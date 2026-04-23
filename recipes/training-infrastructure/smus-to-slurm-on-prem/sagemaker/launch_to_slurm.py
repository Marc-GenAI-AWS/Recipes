"""
launch_to_slurm.py — run this from SMUS JupyterLab to submit a training job
to on-prem Slurm. Mirrors SageMaker's Estimator + .fit() shape.

Usage (from a terminal in your SMUS JupyterSpace):

    python sagemaker/launch_to_slurm.py

Edit the CONFIG block below first. The script:
  1. Resolves the SMUS kernel's AWS credentials (project role) via boto3.
  2. POSTs an sbatch job to slurmrestd — which is reachable via the
     Cloudflare Tunnel URL you paste below.
  3. Polls until the job reaches a terminal state.
  4. Prints the summary; the MLflow run shows up in SMUS → Experiments.

Network transport — opaque to this module
-----------------------------------------
SLURM_REST_URL is plain HTTPS. Behind it the chain is:

    script (SMUS)  →  Cloudflare edge  →  cloudflared on the cluster
                                           →  slurmrestd on 127.0.0.1:6820

In production the URL would resolve to a private IP over Direct Connect /
VPN instead. This file does not change — the bridge is a transport concern.

Identity model for the PoC
--------------------------
SLURM_JWT is minted for SLURM_USER (e.g. "alice") so the job runs as that
POSIX user on-prem — it inherits that user's pip-installed torch / mlflow
and their writable home directory. Production replaces this with per-user
JWTs minted from the SMUS user's OIDC identity + pre-provisioned UIDs.

AWS credentials for MLflow logging from the on-prem job are auto-resolved
from the notebook kernel's boto3 session (same implicit-role behavior
SageMaker's Estimator uses) and forwarded into the Slurm job environment.
"""

from __future__ import annotations

# ─── EDIT BEFORE RUNNING ─────────────────────────────────────────────────
#
# SLURM_USER must be your POSIX login on the on-prem box — i.e. the output
# of `whoami` (or `echo $USER`) in a shell on that machine. NOT your AWS
# identity, NOT your SMUS username. The JWT below must have been minted for
# this same user, and that user must already have torch / torchvision
# installed under python3.11 (the sbatch script reuses their packages).

SLURM_REST_URL      = "<paste tunnel URL — e.g. https://xyz.trycloudflare.com>"
SLURM_JWT           = "<paste scontrol token output (minted for SLURM_USER)>"
SLURM_USER          = "<your POSIX username on the on-prem box — output of `whoami` there>"
SLURM_REPO_PATH     = "<paste on-prem repo clone path — e.g. /home/<SLURM_USER>/smus-to-slurm-on-prem>"
MLFLOW_TRACKING_URI = "<paste tracking server ARN>"

HYPERPARAMETERS = {
    "epochs": 5,
    "batch_size": 128,
    "lr": 1e-3,
    # "subset": 2000,   # uncomment to train on a small slice for debugging
}

# ─── END EDIT ────────────────────────────────────────────────────────────


import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import boto3
import requests

SLURM_API = "/slurm/v0.0.40"
TERMINAL_STATES = {
    "COMPLETED", "FAILED", "CANCELLED", "TIMEOUT",
    "NODE_FAIL", "OUT_OF_MEMORY", "BOOT_FAIL", "DEADLINE",
}


@dataclass
class SlurmTrainingLauncher:
    """SageMaker-Estimator-shaped launcher for on-prem Slurm."""

    # ---- What to train ------------------------------------------------------
    entry_point: str = "train.py"          # module file the sbatch wrapper runs
    source_dir: str = "on-prem/training"   # relative to repo_path on the cluster
    hyperparameters: dict[str, Any] = field(default_factory=dict)

    # ---- Where to submit ---------------------------------------------------
    rest_url: str = ""
    jwt: str = ""
    slurm_user: str = "slurm"
    repo_path: str = ""

    # ---- MLflow ------------------------------------------------------------
    mlflow_tracking_uri: str = ""
    mlflow_experiment: str = "smus-to-dgx"

    # ---- Slurm resource shape ---------------------------------------------
    partition: str = "gpu"
    gres: str = "gres/gpu:1"
    time_limit_min: int = 30
    job_name: str = "smus-train"

    # ---- Polling + HTTP ----------------------------------------------------
    poll_secs: int = 10
    request_timeout: int = 30

    # ---- AWS credentials (auto-resolved if not provided) -------------------
    aws_credentials: tuple[str, str, str | None] | None = None
    aws_region: str | None = None

    # ---- Public API --------------------------------------------------------

    def ping(self) -> dict:
        r = requests.get(self._url("/ping"), headers=self._headers(),
                         timeout=self.request_timeout)
        r.raise_for_status()
        return r.json()

    def fit(self, on_poll: Callable[[str], None] | None = None) -> dict:
        job_id = self._submit()
        return self._wait(job_id, on_poll=on_poll)

    # ---- Internals ---------------------------------------------------------

    def _headers(self) -> dict:
        return {
            "X-SLURM-USER-NAME": self.slurm_user,
            "X-SLURM-USER-TOKEN": self.jwt,
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self.rest_url.rstrip('/')}{SLURM_API}{path}"

    def _resolve_aws(self) -> tuple[tuple[str, str, str | None], str]:
        if self.aws_credentials is None:
            sess = boto3.Session()
            c = sess.get_credentials().get_frozen_credentials()
            creds = (c.access_key, c.secret_key, c.token)
            region = self.aws_region or sess.region_name or "us-west-2"
        else:
            creds = self.aws_credentials
            region = self.aws_region or "us-west-2"
        return creds, region

    def _build_env(self) -> list[str]:
        (ak, sk, tok), region = self._resolve_aws()
        hp = self.hyperparameters
        env = [
            f"REPO_PATH={self.repo_path}",
            f"TRAIN_DIR={self.repo_path}/{self.source_dir}",
            f"EPOCHS={hp.get('epochs', 3)}",
            f"BATCH_SIZE={hp.get('batch_size', 128)}",
            f"LR={hp.get('lr', 1e-3)}",
            f"MLFLOW_TRACKING_URI={self.mlflow_tracking_uri}",
            f"MLFLOW_EXPERIMENT_NAME={self.mlflow_experiment}",
            f"AWS_ACCESS_KEY_ID={ak}",
            f"AWS_SECRET_ACCESS_KEY={sk}",
            f"AWS_DEFAULT_REGION={region}",
            "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        ]
        if tok:
            env.append(f"AWS_SESSION_TOKEN={tok}")
        if hp.get("subset"):
            env.append(f"SUBSET={hp['subset']}")
        return env

    def _submit(self) -> int:
        script = (
            "#!/bin/bash\n"
            "set -euo pipefail\n"
            f'cd "{self.repo_path}"\n'
            f"bash {self.source_dir}/sbatch-train.sh\n"
        )
        payload = {
            "script": script,
            "job": {
                "name": self.job_name,
                "partition": self.partition,
                "tres_per_node": self.gres,
                "current_working_directory": self.repo_path,
                "environment": self._build_env(),
                "time_limit": {"set": True, "number": self.time_limit_min},
                "standard_output": "/tmp/smus-train-%j.out",
                "standard_error":  "/tmp/smus-train-%j.err",
            },
        }
        r = requests.post(self._url("/job/submit"), headers=self._headers(),
                          data=json.dumps(payload), timeout=self.request_timeout)
        body = r.json()
        if r.status_code >= 400 or body.get("errors"):
            raise RuntimeError(f"submit failed: HTTP {r.status_code} {body}")
        return int(body["job_id"])

    def _wait(self, job_id: int, on_poll: Callable[[str], None] | None) -> dict:
        while True:
            r = requests.get(self._url(f"/job/{job_id}"),
                             headers=self._headers(), timeout=self.request_timeout)
            r.raise_for_status()
            jobs = r.json().get("jobs", [])
            if not jobs:
                raise RuntimeError(f"job {job_id} not visible via slurmrestd")
            j = jobs[0]
            state = (j.get("job_state") or ["UNKNOWN"])[0]
            if on_poll is not None:
                on_poll(state)
            if state in TERMINAL_STATES:
                return {
                    "job_id": job_id,
                    "state": state,
                    "exit_code": j.get("exit_code", {}).get("return_code", {}).get("number"),
                    "start_time": j.get("start_time", {}).get("number"),
                    "end_time":   j.get("end_time", {}).get("number"),
                    "node_list":  j.get("nodes"),
                }
            time.sleep(self.poll_secs)


# ─── Driver ──────────────────────────────────────────────────────────────

def _log_state(state, last=[None]):
    if state != last[0]:
        print(f"state → {state}")
        last[0] = state


def main() -> int:
    # Fail fast if any CONFIG placeholder wasn't replaced.
    for name, value in dict(
        SLURM_REST_URL=SLURM_REST_URL, SLURM_JWT=SLURM_JWT,
        SLURM_USER=SLURM_USER, SLURM_REPO_PATH=SLURM_REPO_PATH,
        MLFLOW_TRACKING_URI=MLFLOW_TRACKING_URI,
    ).items():
        if value.startswith("<"):
            sys.exit(f"ERROR: {name} is still a placeholder — edit this file first.")

    launcher = SlurmTrainingLauncher(
        entry_point="train.py",
        source_dir="on-prem/training",
        rest_url=SLURM_REST_URL,
        jwt=SLURM_JWT,
        slurm_user=SLURM_USER,
        repo_path=SLURM_REPO_PATH,
        mlflow_tracking_uri=MLFLOW_TRACKING_URI,
        hyperparameters=HYPERPARAMETERS,
    )

    print(f"pinging {SLURM_REST_URL} ...")
    launcher.ping()
    print("endpoint OK")

    print(f"submitting job as user={SLURM_USER}, hyperparameters={HYPERPARAMETERS}")
    result = launcher.fit(on_poll=_log_state)
    print()
    print("=" * 60)
    print(json.dumps(result, indent=2, default=str))
    print("=" * 60)
    print(f"MLflow run: SMUS → Experiments → {launcher.mlflow_experiment}"
          f" → runName 'slurm-{result['job_id']}'")
    return 0 if result["state"] == "COMPLETED" else 1


if __name__ == "__main__":
    sys.exit(main())
