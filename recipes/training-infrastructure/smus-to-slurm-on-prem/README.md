# SageMaker Unified Studio to On-Prem Slurm Basic Framework

End-to-end proof of viability for using **SageMaker Unified Studio (SMUS)** as a consolidation plane — IDE, catalog, experiment tracking, orchestration — over **on-prem** Slurm / NVIDIA SuperPod compute. Compute and data stay on-prem; only metadata flows to AWS.

See [`poc-sketch.md`](./poc-sketch.md) for the architecture rationale, decision points, and production-vs-PoC tradeoffs.

This README is the **runbook** — clone the repo, follow the steps in order, and you have a working bridge.

## Repo layout

```
on-prem/          # runs on your Slurm / SuperPod side
  slurm/          # single-node Slurm install + slurmrestd with JWT auth
  tunnel/         # Cloudflare Quick Tunnel to expose slurmrestd to AWS
  training/       # train.py module + sbatch-train.sh
sagemaker/
  launch_to_slurm.py            # runnable dispatch script — SageMaker-Estimator-shaped
  01-develop-in-smus.ipynb      # interactive dev on a small subset
poc-sketch.md     # architecture doc — rationale, tradeoffs, production path
```

## Prerequisites

**On-prem side** (this PoC was built against an NVIDIA DGX Spark; the primary target is NVIDIA SuperPod / DGX, i.e. **aarch64**):
- Ubuntu 24.04 aarch64 (other Debian-family distros likely fine; adjust the apt lines if needed). The Cloudflare installer in `on-prem/tunnel/run-quick-tunnel.sh` hardcodes the arm64 `.deb` — edit it for x86.
- `python3.11` on `$PATH` for the POSIX user the Slurm job will run as
- That user must already have `torch` and `torchvision` importable under python3.11 — the sbatch script checks and fails fast if missing. Install once with `python3.11 -m pip install --user torch torchvision` (pick the wheel matching your CUDA / arch from pytorch.org)
- sudo access
- A reachable GPU (`nvidia-smi` works)

**AWS side** (this README assumes you already have these):
- AWS CLI installed and configured with credentials for the target account
- A SageMaker Unified Studio domain with a project
- A managed MLflow tracking server in that project
- An IAM user (or principal via Roles Anywhere in production) that can write to MLflow

> **Don't have these yet?** See [`deploy-smus/README.md`](deploy-smus/README.md) for a zero-to-working walkthrough — AWS CLI install, deploying a SMUS domain via AWS's quick-setup template, and a Python driver (`deploy-smus/deploy_smus_resources.py`) that creates a project in an existing domain and prints the exact CONFIG values you'll need below.

## How to reproduce end-to-end

A condensed walkthrough. Each step links to the detailed section below.

### On the on-prem box (one-time)

```bash
git clone https://github.com/Marc-GenAI-AWS/smus-to-slurm-on-prem.git
cd smus-to-slurm-on-prem

sudo bash on-prem/slurm/install-slurm.sh         # installs Slurm + munge, starts daemons
sudo bash on-prem/slurm/install-slurmrestd.sh    # adds slurmrest user + systemd drop-in

on-prem/tunnel/run-quick-tunnel.sh --background  # prints https://*.trycloudflare.com URL
```

Note the tunnel URL. Then mint a JWT for the user the on-prem job should run as (not the `slurm` service user — otherwise the job can't read your pip-installed packages or write to your home):

```bash
sudo -u slurm scontrol token username=$USER lifespan=7200
```

Copy that token.

### In SMUS JupyterLab

1. Clone this repo into your JupyterSpace (or sync via the SMUS domain-level Git integration):

   ```bash
   git clone https://github.com/Marc-GenAI-AWS/smus-to-slurm-on-prem.git
   cd smus-to-slurm-on-prem
   ```

2. *(Optional)* Open `sagemaker/01-develop-in-smus.ipynb` and run it — iterates on a 2 000-sample subset to confirm the training module works in the kernel.

3. Edit the `CONFIG` block at the top of `sagemaker/launch_to_slurm.py`. Here is exactly where each value comes from:

   | Variable | Where to get it |
   |---|---|
   | `SLURM_REST_URL` | The `https://*.trycloudflare.com` URL printed by `on-prem/tunnel/run-quick-tunnel.sh --background`. If you missed it, `grep trycloudflare on-prem/tunnel/cloudflared.log` on the on-prem box. |
   | `SLURM_JWT` | On the on-prem box, run `sudo -u slurm scontrol token username=$USER lifespan=7200` and copy the value after `SLURM_JWT=`. Must be minted for the same user as `SLURM_USER`. |
   | `SLURM_USER` | **Your POSIX login on the on-prem box** — output of `whoami` in a shell there. NOT your AWS / SMUS username. |
   | `SLURM_REPO_PATH` | Absolute path where you cloned this repo on the on-prem box. Run `pwd` from inside the clone, e.g. `/home/alice/smus-to-slurm-on-prem`. |
   | `MLFLOW_TRACKING_URI` | The tracking server ARN. Get it from **SMUS → Project → MLflow tracking server** in the console, or run `aws sagemaker list-mlflow-tracking-servers --region <your-region>` and copy `TrackingServerArn`. (`deploy-smus/deploy_smus_resources.py` also prints this for you.) |
   | `HYPERPARAMETERS` | Dict — edit in place. `epochs`, `batch_size`, `lr` are required; uncomment `subset` to train on a slice for a fast smoke test. |

   AWS credentials are not in the `CONFIG` — the script resolves them from the kernel's boto3 session and forwards them to the on-prem job.

4. Open a JupyterSpace terminal and run:

   ```bash
   python sagemaker/launch_to_slurm.py
   ```

5. Watch the script:
   - ping the endpoint
   - submit the job (prints a `job_id`)
   - stream state transitions: `PENDING → RUNNING → COMPLETED`
   - print a JSON summary and a pointer to the MLflow run

6. Open **SMUS → Experiments → `smus-to-dgx`**. The new run has per-epoch `train_loss` / `val_loss` / `val_acc`, your hyperparameters, and tags for `hostname` and `artifact_uri_onprem`. The weight file stayed on the DGX — only metadata crossed.

### Expected shape of a successful run

```
pinging https://proposals-signal-design-uses.trycloudflare.com ...
endpoint OK
submitting job as user=alice, hyperparameters={'epochs': 5, 'batch_size': 128, 'lr': 0.001}
state → PENDING
state → RUNNING
state → COMPLETED

============================================================
{
  "job_id": 8,
  "state": "COMPLETED",
  "exit_code": 0,
  "start_time": ...,
  "end_time":   ...,
  "node_list":  "gpu-node-01"
}
============================================================
MLflow run: SMUS → Experiments → smus-to-dgx → runName 'slurm-8'
```

End-to-end: ~90 seconds on a GB10 for 5 epochs of full FashionMNIST.

## Run order (detailed)

### 1. Stand up Slurm on the on-prem box

```bash
sudo bash on-prem/slurm/install-slurm.sh
```

Installs `slurm-wlm`, `slurmrestd`, `munge`; places the configs in `/etc/slurm/`; mints a JWT HS256 key; starts `slurmctld` + `slurmd`. Verify:

```bash
sinfo
srun --gres=gpu:1 nvidia-smi --query-gpu=name --format=csv,noheader
```

Before running on a real multi-node cluster, edit `on-prem/slurm/slurm.conf` (cluster name, node topology) and distribute configs + the munge key.

### 2. Expose Slurm over REST

```bash
sudo bash on-prem/slurm/install-slurmrestd.sh
```

Creates a dedicated `slurmrest` user, writes a systemd drop-in, starts `slurmrestd` on `0.0.0.0:6820` with JWT auth, and pings the API to confirm.

Mint a JWT any time with:

```bash
sudo -u slurm scontrol token lifespan=3600
```

### 3. Expose it to AWS via Cloudflare Tunnel

```bash
on-prem/tunnel/run-quick-tunnel.sh --background
```

Installs `cloudflared` if missing, launches a **Quick Tunnel** (`https://*.trycloudflare.com`), and prints the URL. Smoke test from any machine:

```bash
TOKEN=$(sudo -u slurm scontrol token lifespan=3600 | sed 's/^SLURM_JWT=//')
URL=<paste-tunnel-url>
curl -H "X-SLURM-USER-NAME: slurm" -H "X-SLURM-USER-TOKEN: $TOKEN" \
  "$URL/slurm/v0.0.40/ping"
```

> **Ephemeral by design.** The Quick Tunnel subdomain rotates every restart. Fine for a PoC; for anything longer, use a [named tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/) (free, stable URL against a Cloudflare-managed domain).

### 4. Train a model on-prem (end-to-end validation)

The training code is a single Python module with two entry points:

- **Module**: `on-prem/training/train.py` — exposes `train(epochs, batch_size, lr, subset, ...)`. The notebook imports and calls this directly for interactive iteration (small subset, quick loss curves).
- **Batch**: `on-prem/training/sbatch-train.sh` — the Slurm submission script that the SMUS Workflows DAG will POST to `slurmrestd`. Passes hyperparameters through env vars (`EPOCHS`, `BATCH_SIZE`, `LR`, `SUBSET`).

Smoke test the module directly (no Slurm):

```bash
python3.11 on-prem/training/train.py --epochs 1 --subset 1000
```

Submit the same code via Slurm:

```bash
SUBSET=1000 EPOCHS=1 sbatch on-prem/training/sbatch-train.sh
tail -f smus-train-*.out
```

Both paths log to the MLflow tracking server at `MLFLOW_TRACKING_URI` (a local `./mlruns/` directory if unset — fine for DGX-standalone testing). Artifacts are saved to `~/models/` and only their URIs are logged to MLflow, preserving the "data and weights never leave on-prem" property.

### 5. Dispatch from SMUS JupyterLab

The PoC demonstrates the scientist workflow end-to-end inside **SMUS JupyterLab**:

```
sagemaker/
  launch_to_slurm.py            # runnable script — submits the job to on-prem Slurm
  01-develop-in-smus.ipynb      # interactive dev on a 2000-sample subset
```

**Why notebook-direct (not a DAG)?** Running under the user's JupyterLab kernel preserves the identity chain (SMUS user → project role → script → slurmrestd call). When you later want per-user passthrough to on-prem (OIDC federation into Slurm), only the JWT-minting step moves; the surface stays the same. A SMUS Workflows DAG would inject a service principal between the user and the cluster — fine for production scheduled jobs, wrong for the *"author and dispatch"* scientist story.

**In SMUS JupyterLab:**

1. Clone this repo into the project space (or sync it via the SMUS Git integration at the domain level).
2. Open `sagemaker/01-develop-in-smus.ipynb` for interactive iteration on a small subset. Plots the loss curve inline.
3. Edit the `CONFIG` block at the top of `sagemaker/launch_to_slurm.py`:

   | Variable | What |
   |---|---|
   | `SLURM_REST_URL` | tunnel URL from step 3 |
   | `SLURM_JWT` | `scontrol token` output minted for `SLURM_USER` |
   | `SLURM_USER` | **your POSIX login on the on-prem box** — what `whoami` prints in a shell on that machine (same user the JWT was minted for) |
   | `SLURM_REPO_PATH` | on-prem clone path, e.g. `/home/alice/smus-to-slurm-on-prem` |
   | `MLFLOW_TRACKING_URI` | tracking server ARN |
   | `HYPERPARAMETERS` | dict of epochs / batch_size / lr / optional subset |

   **AWS credentials are not in the CONFIG.** The script runs under the SMUS project role (Identity Center → project role → kernel); it reads the credentials boto3 has already resolved (`Session().get_credentials().get_frozen_credentials()`) and forwards them to the Slurm job. Temporary, role-based, auto-refreshed.

4. Open a terminal in your JupyterSpace and run:

   ```bash
   python sagemaker/launch_to_slurm.py
   ```

   The script pings the endpoint, submits, streams state transitions, prints a summary, and points you at the MLflow run.

**What to expect:**

- Console output shows the Slurm `job_id`, state transitions (`PENDING → RUNNING → COMPLETED`), and a JSON summary.
- In SMUS → Experiments, a new run appears in the `smus-to-dgx` experiment with params, per-epoch metrics, and `hostname` + `artifact_uri_onprem` tags.
- No dataset or model weight crosses the network boundary.

> **Credential note:** forwarding the kernel's resolved role credentials is a PoC-appropriate shortcut — temporary creds, never long-lived IAM user keys, auto-refreshed through the kernel's normal provider chain. Production upgrades this to **IAM Roles Anywhere**: the on-prem job presents an X.509 cert from the on-prem PKI, trades it directly for STS creds, and removes the notebook from the credential path entirely. See [`poc-sketch.md`](./poc-sketch.md).

## Appendix · Dispatch options considered

Three ways to submit a training job from SMUS to on-prem Slurm were evaluated. This repo implements **Option 1**. The other two are documented here because they are the realistic production paths, and which one you pick depends on your orchestration needs — not on what SMUS supports.

### Option 1 · Notebook-direct (this repo)

A runnable script in SMUS JupyterLab (`sagemaker/launch_to_slurm.py`) calls `slurmrestd` over HTTPS. The scientist iterates on a small subset via the `01-develop-in-smus.ipynb` notebook, then runs the script from a JupyterSpace terminal to fire the full training on the on-prem GPU.

- **Pros.** No orchestration ceremony. Short feedback loop. Preserves the SMUS user's identity chain — when you later want per-user passthrough to Slurm / Run:AI, only the JWT-minting step changes; the notebook surface stays the same. Fits the "scientist authors in JupyterLab" story exactly.
- **Cons.** No retries, schedules, or workflow-level audit trail. Not appropriate for unattended / scheduled retraining pipelines.
- **When this is right.** PoC validation, interactive experimentation, demos, any case where the human is in the loop.

### Option 2 · SMUS Workflows DAG with a Lambda bridge

SMUS Workflows (MWAA Serverless under the hood) only accepts DAGs converted to YAML. The [AWS converter](https://docs.aws.amazon.com/mwaa/latest/mwaa-serverless-userguide/workflows-migrate.html) (`python-to-yaml-dag-converter-mwaa-serverless`) rejects `PythonOperator`, `BashOperator`, `HttpOperator`, and the TaskFlow `@task` decorator. The only supported operators are AWS-integration ones: `LambdaInvokeFunctionOperator`, `StepFunctionStartExecutionOperator`, the SageMaker family, EMR, S3, Bedrock, etc.

So the DAG cannot call slurmrestd directly. The workaround is a **Lambda-as-bridge** pattern:

1. Deploy a Lambda that contains the `submit / poll / report` Python logic and can reach the tunnel URL.
2. Store the JWT in Secrets Manager; Lambda execution role reads it at runtime.
3. DAG YAML = `LambdaInvokeFunctionOperator(submit)` → `LambdaInvokeFunctionOperator(poll)` → `LambdaInvokeFunctionOperator(report)`.

- **Pros.** Native SMUS Workflows integration. Retries, schedules, task-level logs. Fits a "nightly retrain" or "retrain-on-data-arrival" pattern. Lambda isolates the credential handling from the DAG YAML.
- **Cons.** Adds a service (Lambda) with its own IAM role, deployment pipeline, and cold starts. User identity is lost at the Lambda boundary unless the invocation payload carries an OIDC token that Lambda re-validates. More moving parts for a PoC.
- **When this is right.** Unattended scheduled training, multi-step pipelines with data prep → train → eval → register, production orchestration shared by a team.

### Option 3 · Classic MWAA (not Serverless)

Classic MWAA runs a real Airflow environment and accepts arbitrary Python DAGs with any operator. A `PythonOperator` or `HttpOperator` that calls slurmrestd works as-is — no YAML conversion, no Lambda bridge.

- **Pros.** The Python DAG we originally wrote would just run. Full Airflow feature set. Fewest moving parts of the three if you want a DAG.
- **Cons.** Higher fixed cost (always-on environment). Longer provisioning time. Not clear whether SMUS projects can point at a classic MWAA environment in all account configurations — worth confirming with AWS SA.
- **When this is right.** You already run classic MWAA, or you want the richest Airflow surface and accept the cost.

### Picking one

| | Iteration / demo | Scheduled production | Lowest infra cost |
|---|---|---|---|
| Notebook-direct | ✓ | ✗ | ✓ |
| DAG + Lambda bridge | ✗ | ✓ | moderate |
| Classic MWAA | moderate | ✓ | ✗ |

For a 2-week proof of viability, Option 1 is the fastest path to a live demo and tells the SMUS-as-consolidation-plane story most directly. For production retraining pipelines, Option 2 or 3 — the choice between them turns on whether you want to stay on Serverless (cheaper, more constrained) or classic MWAA (richer, always-on).

## Tested environment

- NVIDIA DGX Spark (GB10, 20 cores, 122 GB RAM, 1 GPU)
- Ubuntu 24.04.4 LTS aarch64
- Slurm 23.11.4, cloudflared 2026.3.0
- SMUS domain in `us-west-2`

## Security notes

Read these before running anything in this repo against a cluster you care about. This is a proof-of-viability, not a hardened deployment.

- **AWS credentials are forwarded into the Slurm job environment.** `launch_to_slurm.py` resolves the kernel's boto3 credentials and injects `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN` into the slurmrestd submission payload. Those env vars land in the `environment` list of the job record and may be visible in Slurm job accounting, slurmctld logs, or `scontrol show job` output depending on how your cluster is configured. **Only use short-lived STS / role credentials** — never long-lived IAM user access keys. Do not run this as-is against a production Slurm install that archives job environments.
- **JWT auth is HS256 with a shared secret, not OIDC.** `install-slurm.sh` generates a local HS256 key for slurmrestd. That is fine for a single-machine PoC; production should federate to Cognito or Keycloak with RS256 and per-user claims.
- **The Cloudflare Quick Tunnel exposes slurmrestd on a public `https://*.trycloudflare.com` URL.** Anyone holding a valid JWT can submit jobs. The tunnel URL rotates on restart, but while it is up it is internet-reachable. Keep JWT lifespans short, rotate the HS256 key if you suspect leakage, and prefer a named tunnel with Cloudflare Access in front for anything beyond iteration.
- **MLflow logging uses forwarded AWS credentials.** Production should replace this with IAM Roles Anywhere: the on-prem job presents an X.509 cert, trades it for STS creds on the node, and the notebook is not in the credential path. See [`poc-sketch.md`](./poc-sketch.md).
- **No CSRF / rate-limit / WAF in front of slurmrestd.** Do not leave the tunnel up unattended.

## Known caveats (what this PoC does not prove)

- Quick Tunnel URL rotates on every `cloudflared` restart — not stable across sessions.
- JWT tokens expire on the timer you set; the DAG does not auto-rotate them yet.
- HS256 shared-secret JWT instead of Cognito/Keycloak RS256 OIDC — simpler for PoC, insufficient for production.
- MLflow logging will use an IAM user's access keys rather than IAM Roles Anywhere + X.509 — see [`poc-sketch.md`](./poc-sketch.md) for the production path.
- Single-node Slurm does not exercise real scheduling (fairshare, multi-node allocation, queue contention).

## Cleanup

```bash
# Stop the tunnel (if backgrounded)
pkill -f 'cloudflared tunnel' || true

# Stop Slurm daemons
sudo systemctl stop slurmrestd slurmd slurmctld munge
```

Packages remain installed — uninstall with `sudo apt-get purge slurm-wlm slurmrestd munge` if needed.
