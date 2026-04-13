# Cross-AZ FSx Lustre + SageMaker Training

**Open source reference architecture for training large genomic foundation
models when your data and GPU capacity live in different availability zones.**

Validated with NVIDIA BioNeMo Evo2 (1B, 7B, and 40B parameter models) reading
training data across AWS availability zones at no measurable cost to per-step
training throughput. Solves the problem of scarce P5/P4de GPU capacity being
available in different AZs than where your data sits.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full architectural rationale,
evidence, and cost analysis. See [LEARNINGS.md](LEARNINGS.md) for deep
technical notes, gotchas, and scaling test results.

---

## Results & Performance

> Like a model card — the numbers are up front so you know what you're
> getting before you read the instructions.

### Validated scaling results

All runs used `micro_batch_size=1`, `seq_length=8192` (2048 for 40B),
`max_steps=10`, training from scratch across AZ boundaries on hg38 genomic
data. FSx Lustre lived in `us-west-2a`; training jobs ran in `us-west-2c`.

| Model | Dataset (bin/idx) | Instance | GPUs | PP | Steady step | Tokens/sec | Peak VRAM | GPU util | Run cost |
|---|---|---|---|---|---|---|---|---|---|
| **Evo2 1B** | 561 MB (10 GB raw) | ml.g5.12xlarge | 4× A10G 24 GB | 4 | **2.16 s** | 3,795 | 15 GB / 24 GB | ~25% | ~$2 |
| **Evo2 1B** | 96 GB (100 GB raw) | ml.g5.12xlarge | 4× A10G 24 GB | 4 | **2.155 s** | 3,802 | 15.4 GB / 24 GB | 24.7% | ~$5 |
| **Evo2 7B** | 561 MB (10 GB raw) | ml.p4d.24xlarge | 8× A100 40 GB | 8 | **2.82 s** | 2,904 | 28 GB / 40 GB | 24.6% | ~$15 |
| **Evo2 40B** | 561 MB (10 GB raw) | ml.p4de.24xlarge | 8× A100 80 GB | 8 | **4.0 s** | ~512 | 80.1 GB / 81.9 GB | ~25% | ~$8 |

### Key findings

**1. Cross-AZ data transfer is not the bottleneck — at any dataset scale.**

Scaling the dataset 171× (561 MB → 96 GB preprocessed) changed steady-state
step time by 0.005 s (0.2%). The training loop reads ~8 KB per step regardless
of total dataset size; the rest of the data sits on Lustre until sampled later.
This validates the core premise: cross-AZ FSx Lustre reads are invisible to
the training loop at genomic foundation model scales.

**2. Model scaling (1B → 7B → 40B) is absorbed by hardware tier upgrades.**

| Scaling step | Param increase | Step time increase |
|---|---|---|
| 1B → 7B | 7× | 1.31× |
| 7B → 40B | 5.7× | 1.42× |
| 1B → 40B | 40× | 1.85× |

Despite a 40× increase in model parameters, step time grew less than 2×
because each hardware tier (A10G → A100 40GB → A100 80GB) brings proportional
compute and memory bandwidth. The cost of larger models is in GPU memory (you
need bigger or more GPUs), not in wall-clock training time per step.

**3. GPU utilization is low (~25%) in these validation runs — by design.**

Pipeline parallelism with `micro_batch_size=1` leaves GPUs idle between
pipeline stages. These runs measure worst-case efficiency. In production with
`micro_batch_size=16–32` and gradient accumulation, utilization typically
reaches 60–80%+. The step times above are a conservative upper bound.

**4. The `40b_nv` model variant has a framework bug in BioNeMo 2.7.1.**

`40b_nv` crashes with `CUDA error: an illegal memory access` during
distributed optimizer setup on every multi-GPU pipeline-parallel configuration
tested (different PP, TP, seq_length — all crash). The vanilla `40b` model
runs identically configured on the same hardware without issues. Always use
`--model-size 40b` (not `40b_nv`) for distributed training. See
[LEARNINGS.md](LEARNINGS.md) "40B results" for the full diagnostic.

**5. GPU memory was the binding constraint, not cross-AZ I/O.**

The 40B run on `ml.p4de.24xlarge` hit 80.1 GB / 81.9 GB VRAM (97%
utilization) at `seq_length=2048`. At `seq_length=8192` it would OOM. This is
the hard wall: the cross-AZ architecture is not what limits scale — GPU
memory is. The fix is `ml.p5.48xlarge` (8× H100 80 GB NVLink), which
provides both more VRAM and ~3× the compute throughput of A100.

### Extrapolation to production (Evo2 40B on ml.p5.48xlarge)

The customer's target: 800 TB of genomic data, 40B parameter model, P5.48xlarge.
Based on the validated results:

| Factor | P4de baseline | P5 expected |
|---|---|---|
| GPU | 8× A100 80 GB | 8× H100 80 GB NVLink |
| Compute throughput | 312 TFLOPS (BF16) | ~990 TFLOPS (BF16) |
| Expected step time (seq=8192) | ~10–12 s (est., needs ≥80 GB) | **~4–5 s** |
| Expected tokens/sec | ~680 | **~1,650–2,050** |
| Max seq_length at micro_batch=1 | 2048 (OOM at 8192) | ~8192 |
| Instance on-demand price | ~$35/hr | ~$98/hr |

Data volume (800 TB on Lustre) will not affect per-step training time — the
561 MB → 96 GB result proves this. The only change at 800 TB is longer data
preprocessing (linear with input size) and higher Lustre storage cost.

> **Before launching a 40B P5 run:** Request the `ml.p5.48xlarge for training
> job usage` quota in AWS Service Quotas well in advance (default is 0 and
> approval takes days). In our testing, `us-west-2c` had P4de capacity
> available within 4 minutes while `us-west-2b` queued 5+ hours — AZ matters.
> See `training_job_config.py` for the full P5 configuration checklist.

---

## What this repo gives you

1. **CDK infrastructure** (Python) that deploys a VPC, FSx for Lustre
   filesystem, IAM roles, and VPC endpoints configured correctly for cross-AZ
   SageMaker training.
2. **Data preparation scripts** that launch throwaway EC2 instances to
   download public genomic data (hg38) and run `preprocess_evo2` to produce
   Megatron-format `.bin`/`.idx` files on the Lustre filesystem.
3. **A SageMaker training job launcher** that mounts FSx Lustre natively via
   `FileSystemConfig` and runs BioNeMo Evo2 fine-tuning with instrumentation
   (nvidia-smi sampling, per-step timing, CloudWatch metrics).
4. **A training container entrypoint script** that handles the triton
   libcuda workaround, optimizer flags, metric collection, and optional
   checkpoint loading.

Everything is declarative. A new deployment takes ~15 minutes from `git clone`
to a running SageMaker training job, plus the time it takes to stage data and
pull the container image.

## Prerequisites

### Accounts and quotas

- **AWS account** with admin access to deploy VPC, IAM, FSx, and SageMaker
  resources. See "AWS IAM permissions" in [Credentials setup](#credentials-setup)
  for the minimum set if you don't want to use admin.
- **NVIDIA NGC account** (free) — sign up at https://ngc.nvidia.com.
  You'll generate an API key during setup.
- **SageMaker service quotas** for the GPU instance types you want to use.
  All of these default to **0** in new accounts and must be requested through
  [AWS Service Quotas](https://console.aws.amazon.com/servicequotas/home?region=us-west-2#!/services/sagemaker/quotas):
  - `ml.g5.12xlarge for training job usage` — for the 1B smoke test (required)
  - `ml.p4d.24xlarge for training job usage` — for the 7B run (optional)
  - `ml.p4de.24xlarge for training job usage` — for the 40B run (optional)

  Each quota request takes hours to a few days for AWS to approve. File them
  **before** you start the walkthrough.

### Local tools

- **Python 3.10+**
- **Node.js 18+** (needed by the AWS CDK CLI)
- **AWS CLI v2** (`aws --version`)
- **AWS CDK CLI** (`npm install -g aws-cdk`)
- **Docker** (for pulling and mirroring the NVIDIA container)

You can run the pre-flight check (below) to verify everything at once.

## Credentials setup

This project needs **two sets of credentials** — AWS (always) and NVIDIA NGC
(for one-time container mirroring). This section walks you through both from
scratch. You can skip any step you've already completed.

### Step 1: NVIDIA NGC API key

Your NGC API key gives you access to **two different NVIDIA assets**, both
of which you'll need to complete the walkthrough:

1. **The BioNeMo Framework container** (`nvcr.io/nvidia/clara/bionemo-framework:2.7.1`)
   — the Docker image that holds the training code, CUDA kernels, and
   framework dependencies. Pulled once via `docker login nvcr.io` + `docker pull`,
   then mirrored to your own ECR repo so SageMaker can pull from there.

2. **Pretrained Evo2 model checkpoints** (e.g. `evo2/1b-8k-bf16:1.0`,
   `evo2/40b-1m-fp8-bf16:1.0`) — the actual trained weights. Downloaded via
   the `download_bionemo_data` CLI **inside** the container. If you only want
   to train from scratch (no warm-start from a pretrained model) you can skip
   this, but for fine-tuning you'll need at least one checkpoint staged.

**Both use the same NGC API key** — just through two different authentication
mechanisms. Docker login for the container, and `~/.ngc/config` (or
`NGC_API_KEY` env var) for the checkpoint downloader. You generate the key
once and it handles both.

#### Generate the key

1. Go to https://ngc.nvidia.com and sign in (create a free account if needed).
2. Click your profile avatar in the top-right corner → **Setup**.
3. Click **Generate API Key** (or **Rotate API Key** if you've created one
   before). Accept the warning that rotating invalidates any existing key.
4. Copy the key immediately — **NGC only shows it once**. Store it in your
   password manager.

   The key looks like: `nvapi-abc123...xyz789` (about 72 characters).

#### Register the key with Docker (for container pulls)

The username is literally the string `$oauthtoken` (not your email, not
your NGC username):

```bash
docker login nvcr.io
Username: $oauthtoken
Password: <paste your NGC API key>
```

Successful output: `Login Succeeded`. The credentials are now stored in
`~/.docker/config.json` and you will not need to enter them again.

#### Register the key with the NGC CLI (for checkpoint downloads)

The `stage_checkpoint_on_lustre.py` script reads your NGC key from
`~/.docker/config.json` automatically and injects it into the EC2 prep
instance, which then passes it to the BioNeMo container as an environment
variable. **You don't need to create `~/.ngc/config` on your laptop** — the
script handles the transfer for you.

If you want to test `download_bionemo_data` locally (inside a container you
run yourself), create `~/.ngc/config`:

```bash
mkdir -p ~/.ngc
cat > ~/.ngc/config <<EOF
[CURRENT]
apikey = <paste your NGC API key>
format_type = json
EOF
chmod 600 ~/.ngc/config
```

This is optional for the main workflow.

### Step 2: AWS credentials

1. If you don't already have AWS credentials configured locally, get them
   from your AWS account admin or create them yourself:
   - **Short-lived session credentials** (preferred, via SSO):
     https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html
   - **Long-lived access keys** (simpler, less secure): IAM Console → Users →
     your user → Security credentials → Create access key → CLI use case.
2. Configure them with `aws configure`, or set the environment variables
   directly:

   ```bash
   aws configure
   # Or:
   export AWS_ACCESS_KEY_ID=...
   export AWS_SECRET_ACCESS_KEY=...
   export AWS_REGION=us-west-2
   ```

3. Verify it works:

   ```bash
   aws sts get-caller-identity
   ```

   You should see your account ID and IAM ARN.

#### Minimum AWS IAM permissions

If you don't want to use admin, the minimum managed policies needed are:

- `AWSCloudFormationFullAccess` (CDK creates stacks)
- `AmazonEC2FullAccess` (VPC, subnets, security groups, EC2 data prep)
- `AmazonFSxFullAccess` (Lustre filesystem)
- `IAMFullAccess` (creates roles for SageMaker and EC2 — can be scoped down)
- `AmazonS3FullAccess` (SageMaker input/output bucket)
- `AmazonSageMakerFullAccess`
- `AmazonEC2ContainerRegistryFullAccess` (ECR for the BioNeMo image mirror)
- `AmazonSSMFullAccess` (for SSM Session Manager debugging of prep instances)
- `CloudWatchLogsFullAccess`

Production deployments should scope these down further. See the CDK code
for the exact resources each stack creates.

### Step 3: Configure this repo's environment variables

Copy the example environment file and fill it in:

```bash
cp .env.example .env
# Edit .env to set AWS_ACCOUNT_ID to your 12-digit account number
# (the rest have sensible defaults)
source .env
```

Verify everything is set:

```bash
echo "Region:  $AWS_REGION"
echo "Account: $AWS_ACCOUNT_ID"
echo "Image:   $BIONEMO_IMAGE"
```

### Step 4: Mirror the BioNeMo container to your ECR

NVIDIA's BioNeMo image lives on `nvcr.io` which is a private registry. SageMaker
training jobs cannot pull directly from `nvcr.io` — you must **mirror** the
image to your own ECR repository once, then reference the ECR copy from there
on. This is a one-time, ~10-20 minute operation.

```bash
# Pull from NGC (uses credentials from Step 1)
# This is the slow part — ~17 GB download
docker pull nvcr.io/nvidia/clara/bionemo-framework:2.7.1

# Create an ECR repository in your account (one-time)
aws ecr create-repository \
    --repository-name bionemo-framework \
    --region $AWS_REGION

# Log Docker in to your ECR (different from NGC login)
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Tag the image with your ECR URI and push
docker tag nvcr.io/nvidia/clara/bionemo-framework:2.7.1 $BIONEMO_IMAGE
docker push $BIONEMO_IMAGE
```

The push takes 15-30 minutes because of the image size and your upload
bandwidth. Afterward, SageMaker training jobs will pull from your ECR at
much higher speeds (~500 MB/s within AWS vs whatever your local upload is).

### Step 5: Run the pre-flight check

Before deploying anything, verify all credentials and tools are set up:

```bash
./scripts/preflight-check.sh
```

This validates AWS credentials, NGC docker login, ECR repo existence, CDK
bootstrap status, tool versions, and the `BIONEMO_IMAGE` env var. It prints
clear `[OK]` / `[FAIL]` lines for each item and exits non-zero if anything
is missing, so you can script around it in CI. Fix any failures before
proceeding — they will turn into expensive failures later if you don't.

## Quickstart

Assumes you've completed the [Credentials setup](#credentials-setup) section
above and `./scripts/preflight-check.sh` reports all green.

### 1. Clone and install dependencies

```bash
git clone https://github.com/<your-org>/cross-az-fsx-sagemaker.git
cd cross-az-fsx-sagemaker

# CDK dependencies
cd infrastructure
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
```

### 2. Deploy the infrastructure

```bash
cd infrastructure
source .venv/bin/activate
cdk bootstrap aws://${AWS_ACCOUNT_ID}/us-west-2  # first time only
cdk deploy --all --require-approval never
```

This creates:

- **VPC** with public subnets in `us-west-2a`, `us-west-2b`, `us-west-2c`,
  an Internet Gateway, and an S3 Gateway VPC endpoint (required for
  SageMaker VPC-mode jobs to reach S3).
- **Security groups** for Lustre (ports 988, 1018-1023), SageMaker training
  jobs, and throwaway EC2 data prep instances.
- **IAM roles** for SageMaker execution and EC2 data prep (both with
  CloudWatch, S3, and ECR read permissions).
- **FSx for Lustre filesystem** in the first AZ, SCRATCH_2 deployment type,
  1.2 TiB capacity, version 2.15. The data will live here.

Expected deploy time: ~10 minutes. Most of it is the FSx filesystem creation.

### 3. Stage training data

Launch a throwaway EC2 instance that downloads hg38 from UCSC, duplicates it
to reach the target data volume, runs `preprocess_evo2` to produce Megatron
`.bin`/`.idx` files, writes everything to the Lustre filesystem, and
self-terminates.

```bash
cd data_preparation
python scale_data_on_lustre.py \
    --phase-subdir phase_10gb \
    --target-raw-gb 13 \
    --output-prefix hg38_10gb
```

This launches a `g5.4xlarge` in the FSx subnet that runs for ~30-60 minutes
(most of it is the initial ECR image pull). The instance self-terminates when
done. Monitor progress:

```bash
aws ssm start-session --target <instance-id-from-launch-output>
sudo tail -f /var/log/scale_data.log
```

Verify the data landed on Lustre:

```bash
python check_fsx_state.py
```

### 4. (Optional) Stage a pretrained Evo2 checkpoint

If you want to **fine-tune** from a pretrained Evo2 model instead of training
from scratch, stage the checkpoint on Lustre first:

```bash
python stage_checkpoint_on_lustre.py \
    --resource evo2/1b-8k-bf16:1.0 \
    --dest-subdir evo2_1b_8k_bf16
```

This launches a `g5.xlarge` prep instance that mounts Lustre, pulls the
BioNeMo container, runs `download_bionemo_data evo2/1b-8k-bf16:1.0` inside
the container (authenticated with your NGC key), and rsyncs the result to
`/mnt/lustre/checkpoints/evo2_1b_8k_bf16/`. Takes ~20-30 minutes including
the ECR pull.

Available Evo2 checkpoints (pass as `--resource`):

| Resource name | Model size | Approx. checkpoint size |
|---|---|---|
| `evo2/1b-8k-bf16:1.0` | 1B params, 8k context | ~2 GB |
| `evo2/7b-8k:1.0` | 7B params, 8k context | ~14 GB |
| `evo2/7b-1m:1.0` | 7B params, 1M context | ~14 GB |
| `evo2/40b-1m-fp8-bf16:1.0` | 40B params, 1M context | ~80-160 GB |

Run `download_bionemo_data --list-resources` inside the container for the
full catalog.

**If you skip this step**, the training script will train from scratch. For
a scaling validation that's fine — step time is identical with or without a
checkpoint. For a real fine-tuning workflow you'll want a pretrained model.

### 5. Launch the SageMaker training job

```bash
cd ..  # back to repo root

python launch_bionemo_job.py \
    --job-name bionemo-1b-10gb-$(date +%H%M%S) \
    --phase-subdir phase_10gb \
    --preproc-prefix hg38_10gb \
    --ckpt-subdir checkpoints/evo2_1b_8k_bf16 \
    --model-size 1b_nv \
    --instance-type ml.g5.12xlarge \
    --max-steps 10 \
    --micro-batch-size 1 \
    --seq-length 8192 \
    --devices 4 \
    --tensor-parallel 1 \
    --pipeline-parallel 4 \
    --activation-ckpt-layers 5 \
    --max-runtime-seconds 5400
```

Omit `--ckpt-subdir` to train from scratch. Include it to fine-tune from the
checkpoint you staged in Step 4.

The script uploads the entrypoint to S3, creates a SageMaker training job
with `FileSystemDataSource` pointing at your Lustre filesystem, and targets a
subnet in a **different AZ** than the filesystem (so every read crosses the AZ
boundary). Monitor the job:

```bash
aws sagemaker describe-training-job \
    --training-job-name <job-name> \
    --query 'TrainingJobStatus' --output text

aws logs tail /aws/sagemaker/TrainingJobs --follow \
    --log-stream-name-prefix <job-name>
```

Expected cost: ~$2-5 per run on `ml.g5.12xlarge`. The training will complete
10 steps and upload a model artifact to S3.

## Repository layout

```
cross-az-fsx-sagemaker/
├── README.md                        # This file
├── ARCHITECTURE.md                  # Architecture doc with cost analysis
├── LEARNINGS.md                     # Deep technical notes + gotchas
├── LICENSE                          # Apache 2.0
├── infrastructure/                  # CDK stacks
│   ├── app.py                       # Stack entrypoint
│   ├── requirements.txt
│   ├── cdk.json
│   └── stacks/
│       ├── network_stack.py         # VPC, subnets, SGs, VPC endpoints
│       ├── iam_stack.py             # SageMaker + EC2 data prep roles
│       └── lustre_stack.py          # FSx for Lustre filesystem
├── data_preparation/                # Throwaway EC2 data prep scripts
│   ├── _ec2_launcher_common.py      # Shared helpers (stack outputs, AMI lookup)
│   ├── scale_data_on_lustre.py     # Stage hg38 + run preprocess_evo2
│   ├── stage_checkpoint_on_lustre.py  # Download NGC checkpoint onto Lustre
│   └── check_fsx_state.py           # Verification helper
├── training_container/
│   └── bionemo_entrypoint.sh        # Runs inside BioNeMo container on SageMaker
├── launch_bionemo_job.py            # SageMaker training job launcher
├── scripts/
│   └── preflight-check.sh           # Validates credentials + tools before deploy
├── .env.example                     # Template for local environment variables
└── examples/
    └── run_scaling_test.sh          # End-to-end scaling test script
```

## Environment variables

All scripts read their configuration from environment variables. Canonical
source of truth is [`.env.example`](./.env.example) — copy it to `.env`,
fill in your values, and `source .env` before running anything. The
[pre-flight check](./scripts/preflight-check.sh) validates each one.

| Variable | Default | Purpose |
|---|---|---|
| `AWS_REGION` | `us-west-2` | Region to deploy and operate in |
| `AWS_ACCOUNT_ID` | **(required)** | 12-digit AWS account ID, used to build ECR URIs |
| `BIONEMO_IMAGE` | **(required)** | ECR URI of your mirrored BioNeMo container |
| `NETWORK_STACK` | `CrossAzFsxNetwork` | CDK stack name (override for multi-tenant) |
| `IAM_STACK` | `CrossAzFsxIam` | CDK stack name |
| `LUSTRE_STACK` | `CrossAzFsxLustre` | CDK stack name |

**Note**: the NGC API key is NOT an environment variable. It lives in
`~/.docker/config.json` via `docker login nvcr.io` (see
[Credentials setup](#credentials-setup) Step 1).

## Cleanup

When you're done validating:

```bash
# Destroy SageMaker training jobs (if any are still running)
aws sagemaker list-training-jobs --status-equals InProgress \
    --query 'TrainingJobSummaries[].TrainingJobName' --output text | \
    xargs -I {} aws sagemaker stop-training-job --training-job-name {}

# Destroy all CDK stacks
cd infrastructure
cdk destroy --all --force
```

**Note**: the FSx Lustre filesystem is SCRATCH_2 — data is ephemeral. Any
data on Lustre is lost when you destroy the stack. If you want to preserve
training data across stack destroys, use a PERSISTENT_2 filesystem with S3
Data Repository Association (see ARCHITECTURE.md section "S3 + Lustre
Data Repository Association").

## Validated results

See the [Results & Performance](#results--performance) section at the top
of this document for the full results table, key findings, and extrapolation
to P5.48xlarge. For raw per-iteration timings, VRAM profiles, and deep
diagnostic notes, see [LEARNINGS.md](LEARNINGS.md) "Scaling test results".

## Known issues

- The `40b_nv` model variant in BioNeMo Framework 2.7.1 has a reproducible
  CUDA error on pipeline-parallel multi-GPU training. Use `--model-size 40b`
  (vanilla) instead. See LEARNINGS.md "40B results" for details.
- FSx Lustre versions are managed per-filesystem. The Lustre 2.10 default
  is incompatible with modern Lustre clients — this repo's CDK explicitly
  sets version 2.15 to avoid this.
- SageMaker training containers run without `CAP_SYS_ADMIN`, which means
  you cannot mount arbitrary filesystems from inside the container. Only
  `FileSystemConfig`-supported filesystems (FSxLustre, EFS, FSxOpenZFS)
  work. FSx NetApp ONTAP does **not** work.

## Contributing

Found a bug or improvement? PRs welcome. Please:

1. Preserve the sanitized examples (no hardcoded account IDs, no API keys).
2. Validate changes against a real deployment before merging.
3. Update the relevant docs (ARCHITECTURE.md, LEARNINGS.md, or README.md).

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.

## Acknowledgments

- [NVIDIA BioNeMo Framework](https://github.com/NVIDIA/bionemo-framework)
  for the Evo2 sub-package and container image.
- Arc Institute and Stanford for the [Evo2](https://www.nature.com/articles/s41586-026-10176-5)
  genomic foundation model.
- AWS for FSx for Lustre, SageMaker Training, and the VPC primitives that
  make this architecture possible.
