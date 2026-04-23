# SMUS → On-Prem HPC / SuperPod: PoC Sketch

## Framing

This sketch is written for teams whose center of gravity is **on-prem**: both data and compute live in their datacenter (HPC cluster + NVIDIA SuperPod). Such teams often evaluate SageMaker Unified Studio (SMUS) **not as a compute or data platform**, but as a **user, asset, and experiment consolidation plane**:

- Unified IDE (JupyterLab) for data scientists
- Central catalog / project governance
- Managed MLflow for experiment + model registry
- SMUS Workflows (managed Airflow inside the project) for orchestrating training runs
- IAM Identity Center as the SSO front door

Everything heavy — datasets, GPUs, training jobs — stays on-prem. SMUS is the control surface; the compute plane is Slurm or Run:AI on their own hardware.

This constraint shapes every design decision below. The bridge must be **thin enough that SMUS earns its keep as a consolidation layer** without becoming a bottleneck or a data-movement tax.

> This document was originally drafted as a scoping sketch for a specific engagement; the framing has been generalized for public readers but the recommendations still read as opinionated defaults rather than a neutral survey. Adapt to your environment.

## Scheduler recommendation

**Lead with Run:AI** if SuperPod is the primary training target:
- NVIDIA-native post-acquisition, purpose-built for GPU fractioning on DGX/SuperPod
- Mature REST API + Python client (`runapy`) + OIDC — trivial to trigger from a SMUS Workflows DAG or a notebook
- Lower custom-glue cost on the SMUS side

**Slurm** is viable if HPC dominates or the team already operates it at scale. Tradeoff: the HPC team must own `slurmrestd` + JWT auth (Cognito or Keycloak-backed RS256). Workable, but operationally heavier than Run:AI's hosted control plane.

For the PoC, pick one. Recommend **Run:AI first** to de-risk the bridge; add Slurm in a second phase.

## Target architecture (PoC scope)

```
┌─────────────────────────── AWS (SMUS) ────────────────────────────┐
│                                                                    │
│  IAM Identity Center ──► SMUS Project                              │
│                            │                                       │
│                            ├── JupyterLab Space (custom BYOI image)│
│                            │     • runai CLI, slurm CLI, ssh       │
│                            │     • mlflow + sagemaker-mlflow       │
│                            │     • boto3, mountpoint-s3 (optional) │
│                            │                                       │
│                            ├── Managed MLflow tracking server      │
│                            │                                       │
│                            └── SMUS Workflows (managed Airflow)    │
│                                  • DAG: submit_runai_job           │
│                                  • DAG: submit_slurm_job (phase 2) │
│                                                                    │
│  Secrets Manager: on-prem OIDC client creds, SSH keys              │
│  IAM Roles Anywhere: trust anchor for on-prem MLflow clients       │
└────────────────────────────────┬───────────────────────────────────┘
                                 │ Direct Connect / Site-to-Site VPN
                                 │ (private, no public egress)
┌────────────────────────────────┴───────────────────────────────────┐
│                           Customer Datacenter                      │
│                                                                    │
│  ┌─────────────────┐         ┌──────────────────────────────────┐  │
│  │ On-prem storage │◄────────┤ Run:AI control plane (REST+OIDC) │  │
│  │  (data stays    │         │   • submits to SuperPod          │  │
│  │   here)         │         └──────────────────────────────────┘  │
│  └────────┬────────┘                                               │
│           │                   ┌──────────────────────────────────┐ │
│           └──────────────────►│ NVIDIA SuperPod (DGX nodes)      │ │
│                               │   • training container           │ │
│                               │   • mlflow logs → AWS (SigV4)    │ │
│                               │   • artifacts → on-prem storage  │ │
│                               └──────────────────────────────────┘ │
│                                                                    │
│  (Phase 2) HPC cluster + slurmrestd                                │
└────────────────────────────────────────────────────────────────────┘
```

### Key property: **data never leaves on-prem**

- Datasets remain on the customer's storage (Lustre / GPFS / NFS / Ceph — whatever they run).
- Training containers mount on-prem storage directly; they do **not** pull from S3.
- Only **metadata** flows to AWS: MLflow run metrics, params, tags, and *pointers* (URIs) to on-prem artifacts.
- Model artifacts can optionally be pushed to S3 for registry/serving if the customer later wants that — but the PoC keeps them on-prem.

This is the single most important design decision. It means SMUS's value is entirely in the consolidation layer, and the bridge's job is to move *control signals and metadata*, not data.

## Component breakdown

### 1. SMUS custom JupyterLab image (BYOI)

Dockerfile baseline — installs the clients the notebook needs to drive on-prem systems:

```dockerfile
FROM public.ecr.aws/sagemaker/sagemaker-distribution:latest-gpu

USER root
RUN apt-get update && apt-get install -y \
    openssh-client slurm-client krb5-user && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    runapy \
    mlflow \
    sagemaker-mlflow \
    apache-airflow-client

# BYOI contract requirements
ENV SAGEMAKER_APP_TYPE_LOWERCASE=jupyterlab
EXPOSE 8888
HEALTHCHECK CMD curl -f http://localhost:8888/jupyterlab/default || exit 1

USER 1000
```

Register in ECR, attach to the SMUS project, select per-space.

### 2. Identity bridge

- **SSO front door**: IAM Identity Center → SMUS.
- **SMUS → Run:AI**: a notebook or SMUS Workflows task fetches an OIDC client secret from Secrets Manager (scoped by SMUS project role), exchanges it for a Run:AI access token, calls the REST API.
- **On-prem training job → AWS MLflow**: the training container runs with X.509 cert from the customer's PKI; cert is trusted by **IAM Roles Anywhere**; container assumes an AWS role and the `sagemaker-mlflow` plugin SigV4-signs MLflow requests.
- **Run-as identity on-prem**: PoC uses a **project-level service identity** (one per SMUS project, mapped to a Run:AI project / Slurm account). See "Identity model" decision point below — whether this is also the right production model depends on the customer's on-prem data access controls, not on any SMUS limitation.

### Why identity on-prem matters (or doesn't)

The schedulers don't need per-user identity to run jobs; a service account works. Identity matters for four downstream concerns, and only one of them is a genuine blocker:

1. **Data authorization on-prem.** The run-as user is what the on-prem filesystem (Lustre/GPFS/NFS/Ceph) sees. If every job runs as `smus-svc`, every user gets the same dataset blast radius. **This is the only one that the scheduler's run-as identity can enforce** — it's a hard requirement if datasets have per-user or per-team ACLs (PII, regulated, compartmentalized research).
2. **Fairshare / quota.** Slurm fairshare and Run:AI project quotas key off account identity. Per-SMUS-project mapping (one account per project) usually gives enough granularity without per-user mapping.
3. **Audit chain of custody.** "Who launched this?" With service identity, the scheduler sees `smus-svc`; the real user is reconstructible from MLflow tags + SMUS Workflows task metadata. Derived rather than authoritative — fine outside regulated settings.
4. **Cost attribution.** GPU-hours per team. Project-level is typically sufficient.

**Decision this actually hinges on**: do on-prem datasets have per-user or per-team access controls enforced at the filesystem layer? If **no** (shared team data, trust boundary is "you got into SMUS"), service identity + project-level mapping is genuinely fine for production — not a stopgap. If **yes**, you need real identity passthrough because the scheduler's run-as user is what the filesystem checks.

### 3. SMUS Workflows DAG (the bridge)

SMUS Workflows is managed Airflow provisioned inside the SMUS project — not a separate service to stand up. DAGs are authored in the project and run in the project's own Airflow environment. The code below is standard Airflow because that is literally what SMUS Workflows executes.

```python
# dags/submit_runai_training.py
from airflow.decorators import dag, task
from datetime import datetime

@dag(start_date=datetime(2026, 4, 1), schedule=None, catchup=False)
def submit_runai_training():

    @task
    def get_runai_token():
        # fetch OIDC client creds from Secrets Manager, exchange for token
        ...

    @task
    def submit_job(token: str, config: dict):
        # POST to Run:AI /api/v1/workloads/trainings
        # body references on-prem dataset path, container image,
        # MLflow tracking URI + AWS role ARN for Roles Anywhere
        ...

    @task
    def poll_until_complete(job_id: str, token: str):
        # poll Run:AI job status; emit to MLflow run via job's own logging
        ...

    token = get_runai_token()
    job_id = submit_job(token, {...})
    poll_until_complete(job_id, token)

submit_runai_training()
```

### 4. Training container contract

On-prem-built container (customer's base image + training code) with a standard entrypoint that:
1. Reads `MLFLOW_TRACKING_URI` (AWS managed MLflow endpoint) from env.
2. Authenticates to AWS via Roles Anywhere using mounted X.509 cert.
3. Starts MLflow run, logs params/metrics/tags.
4. Reads dataset from mounted on-prem path.
5. Writes model artifacts to on-prem path; logs artifact URI (not the artifact) to MLflow.
6. Exits with status code Run:AI can observe.

## Out of scope for PoC

- S3 ↔ on-prem data sync (data stays on-prem, so not needed for v1)
- Slurm path (phase 2)
- User-level identity mapping (service identity is sufficient for validation)
- Model serving / deployment (MLflow registry only)
- Air-gapped SMUS deployment (standard private VPC + DX is enough)

## Example 2-week validation plan

**Week 1 — Foundations**

| Day | Deliverable |
|---|---|
| 1 | AWS account + SMUS domain + Identity Center wired; project created |
| 2 | Direct Connect / VPN confirmed between SMUS VPC and customer lab; reachability test to Run:AI control plane |
| 3 | BYOI image built, pushed to ECR, attached to SMUS project; notebook opens and `runai whoami` succeeds |
| 4 | Managed MLflow server provisioned; Roles Anywhere trust anchor configured against customer PKI |
| 5 | Manual: submit a hello-world Run:AI job from notebook; confirm it lands on SuperPod |

**Week 2 — Bridge + demo**

| Day | Deliverable |
|---|---|
| 6 | SMUS Workflows DAG submits a real training container to Run:AI |
| 7 | Training container logs to AWS MLflow via Roles Anywhere; metrics visible in SMUS MLflow UI |
| 8 | Dataset read from on-prem storage verified; artifacts written to on-prem path; MLflow records URI |
| 9 | End-to-end dry run: scientist logs into SMUS → opens notebook → triggers DAG → watches MLflow |
| 10 | Stakeholder demo + written findings: what worked, what needs phase-2 investment |

## Decision points to surface with stakeholders

1. **Run:AI vs Slurm**: confirm PoC leads with Run:AI; Slurm deferred.
2. **Identity model** — *this is really a data-access-control question, not an IAM question*: are on-prem datasets access-controlled per-user/per-team at the filesystem layer?
   - **No** → project-level service identity is the right answer for PoC **and** production. Map each SMUS project to one Run:AI project / Slurm account. Done.
   - **Yes** → you need real identity passthrough (SAML/OIDC federation into Run:AI; Slurm JWT with user claims; matching POSIX UIDs on the filesystem). Add weeks to the plan and involve their IAM team early.
3. **PKI for Roles Anywhere**: do they have an internal CA we can stand a trust anchor against, or do we need AWS Private CA?
4. **Network path**: Direct Connect (preferred) vs Site-to-Site VPN (acceptable for PoC).
5. **MLflow artifact policy**: URIs only (recommended), or eventual S3 mirror for the registry?
6. **Data catalog integration** — *do they want their on-prem data catalog to integrate with the SMUS Lakehouse catalog, or should SMUS only catalog models/experiments?*
   - **Models/experiments only** (lightest): SMUS catalogs MLflow models + project assets; on-prem datasets remain cataloged wherever they are today (their existing Collibra / Atlan / Alation / Purview / custom). Notebooks reference datasets by on-prem URI. Cheapest, preserves their existing data governance investment.
   - **Federated / metadata-sync** (middle): on-prem dataset metadata is published into SMUS Lakehouse as custom asset types (via DataZone APIs) so scientists can discover datasets in SMUS, but the data itself stays on-prem and queries run there. Requires a one-way metadata sync job and careful schema mapping. This is the "true consolidation" answer.
   - **Lakehouse as system of record** (heaviest): SMUS Lakehouse becomes the authoritative catalog, their existing tool is retired or demoted. Realistically a multi-quarter effort with data-governance stakeholder buy-in — not a SMUS PoC question, a data-strategy question.

   Flag early: option 2 is where most customers land but is often underestimated. It is **out of scope for the 2-week PoC** regardless of which they choose; the PoC validates compute+experiments, the catalog conversation is separate.

## Risks and honest caveats

- **No AWS-published reference architecture** for SMUS→on-prem Slurm/Run:AI. Customer is early — expect to file support cases and work with AWS SAs.
- **Identity passthrough is the hardest long-term problem.** Service identity works for the PoC; production likely wants SAML/OIDC federation into Run:AI and Slurm with user attribution, which is real work.
- **MLflow artifact logging expects a filesystem or S3-compatible store.** Logging URIs-as-tags is a workaround; if they want true artifact tracking without moving data, we need to validate whether an on-prem S3-compatible endpoint (MinIO, etc.) can be registered as the artifact store while the tracking server stays in AWS.
- **SMUS is still maturing.** Features ship frequently; lock the PoC to a specific release and re-validate before production.

## Success criteria

The PoC succeeds if a data scientist can:
1. Log into SMUS with their corporate SSO.
2. Open a notebook that has the on-prem clients pre-installed.
3. Trigger a SMUS Workflows DAG that launches a training job on SuperPod reading on-prem data.
4. See the run appear in managed MLflow within SMUS with metrics and artifact URIs.
5. Do all of the above without any dataset or model weight leaving the customer's datacenter.

If all five work, SMUS-as-consolidation-plane is validated and the team can scope the production build with confidence.

## Live PoC environment (DGX Spark stand-in)

For a hands-on local validation, a DGX Spark (NVIDIA GB10, 20 cores, 122 GB, 1 GPU, Ubuntu 24.04 aarch64) is acting as the on-prem cluster. Build state:

| Component | Configuration | Note |
|---|---|---|
| Slurm 23.11.4 (single-node) | cluster `gpu-node-01`, partition `gpu`, `gpu:1` gres | `srun --gres=gpu:1 nvidia-smi` confirms GPU visibility inside jobs |
| slurmrestd | TCP `0.0.0.0:6820`, plugin `openapi/slurmctld` (`v0.0.40`), JWT HS256 via `/var/spool/slurm/jwt_hs256.key`, runs as `slurmrest` user | `/slurm/v0.0.40/ping` returns 200 |
| Cloudflare Quick Tunnel | `https://*.trycloudflare.com` → `127.0.0.1:6820` | SMUS → tunnel → slurmrestd path verified end-to-end |

### Known caveats for this local PoC (not production)

1. **Cloudflare Quick Tunnel URL is ephemeral.** The `trycloudflare.com` subdomain changes every time `cloudflared` restarts. Fine for iteration. Before a DAG hardcodes the endpoint, either keep the process pinned (systemd unit) or switch to a **named tunnel** on a Cloudflare-managed domain (free tier, stable URL).
2. **JWT tokens are short-lived.** `scontrol token` defaults to 30 min; we use 1 h. Two options for the DAG: (a) mint a token on each run via an SSH/exec step to the cluster, or (b) pre-mint a longer-lived token and store in AWS Secrets Manager, rotating via cron. Option (a) is cleaner and what production should look like.
3. **Auth shortcuts taken vs. the production sketch.** HS256 shared-secret JWT instead of Cognito/Keycloak RS256 OIDC; Slurm job logs to MLflow using an IAM user's access keys instead of IAM Roles Anywhere + X.509. Both are PoC-appropriate simplifications and should be called out in the production scoping conversation.
4. **Single-node "cluster" is not a real scheduling test.** Fairshare, multi-node allocation, and queue contention are not exercised. The PoC validates the bridge and control-plane, not scheduler behavior at scale.
