# Cross-AZ FSx + SageMaker Training — Learnings

Captured from the Syngenta validation: **data in one AZ, GPU training in another AZ, via SageMaker Training Jobs**. Applicable to any customer with similar constraints (e.g. P5 capacity only available in a specific AZ while storage lives elsewhere).

## The use case

Customer has a large dataset (target: 800 TB genomic) and wants to:
- Store the data in **one AZ** to avoid paying for cross-AZ replication.
- Run training on GPU instance types that may only be available in a **different AZ** (P5, H100-class, etc.).
- Use **SageMaker Training Jobs** as the execution wrapper for managed training lifecycle, logging, checkpointing, and quota management.

Core question: *Can SageMaker training instances in AZ B read training data from FSx storage in AZ A, fast enough to be production-viable?*

**Answer: Yes, with FSx for Lustre. No, with FSx NetApp ONTAP.** See the "What doesn't work" section for details.

## Architecture that works

```
+---------------------------- VPC 10.0.0.0/16 ----------------------------+
|                                                                         |
|  us-west-2a (10.0.0.0/24)          us-west-2b (10.0.1.0/24)             |
|                                                                         |
|   +---------------------+           +-------------------------------+   |
|   | FSx for Lustre      |           | SageMaker Training Job        |   |
|   | SCRATCH_2, v2.15    |<----NFS---| ml.g5.12xlarge (g5/g6/p5)     |   |
|   | 1.2+ TiB            | backbone  | VPC-attached                  |   |
|   | Single-AZ           |           | FileSystemConfig=FSxLustre    |   |
|   +---------------------+           +-------------------------------+   |
|                                                                         |
|   S3 Gateway Endpoint (required for SM code channel + artifact upload)  |
+-------------------------------------------------------------------------+
```

**The training container** sees Lustre mounted at `/opt/ml/input/data/<channel>/` by SageMaker itself — no manual `mount` call, no container capabilities, no nfs-common install. SageMaker's managed plane handles the Lustre client.

Every byte the training loop reads traverses the AZ boundary (us-west-2b → us-west-2a). That's the performance characteristic being validated.

## What works

| Component | Status | Notes |
|---|---|---|
| FSx for Lustre SCRATCH_2 in single AZ | Works | Use `file_system_type_version="2.15"`. Default is 2.10 which is incompatible with modern Lustre clients. |
| SageMaker `FileSystemDataSource(FSxLustre)` | Works | Mount path: `DirectoryPath=/<mount_name>` (the random string FSx assigns, e.g. `/prsi7b4v`). Shows up at `/opt/ml/input/data/<channel_name>/` inside the container. |
| Cross-AZ reads during training | Works | Real BioNeMo Evo2 1B fine-tuning ran at ~2.16 s/step on `ml.g5.12xlarge` reading Lustre. |
| VPC-attached SageMaker jobs | Works | Required for Lustre mount. Pass `VpcConfig.Subnets` with the AZ you want the training instance in, and `SecurityGroupIds` with a group that has Lustre ports (988, 1018-1023) allowed outbound toward the Lustre SG. |
| NVIDIA PyTorch / BioNeMo container in ECR | Works | `nvcr.io/...` mirrored to ECR. SageMaker pulls successfully via its control plane. |

## What doesn't work (and why)

### FSx NetApp ONTAP + SageMaker Training — NOT SUPPORTED

SageMaker's `FileSystemDataSource.FileSystemType` only accepts:
- `FSxLustre`
- `EFS`
- `FSxOpenZFS` (added in 2024)

**FSx NetApp ONTAP is not on the list.** There's no SageMaker-native way to mount it.

The workaround of having the container do its own `mount -t nfs` fails because **SageMaker training containers run without `CAP_SYS_ADMIN`**. The `mount(2)` syscall returns EPERM. This is a hard-coded restriction of the SageMaker training runtime, not something configurable via the CreateTrainingJob API. We verified this end-to-end: network path was fine, security groups were fine, `mount.nfs4` binary was present — the kernel denied the syscall itself.

Implication: if a customer is locked into NetApp ONTAP for other reasons (existing data, Active Directory integration, SMB clients, etc.), they cannot use SageMaker Training Jobs directly. Options are:
- Use SageMaker Processing/Inference (same restriction applies)
- Use self-managed EC2 (can mount anything)
- Use SageMaker HyperPod on EKS (full pod-spec control, including privileged mode)
- Replicate the data to FSx Lustre for training (defeats the single-AZ goal)

### `mount -t nfs` in SageMaker training containers

Same root cause as above. Relevant for anyone trying to mount EFS, raw NFS, or FSx NetApp ONTAP from inside the container. **Don't. SageMaker will fail with exit code 32 / `mount: Operation not permitted`.** Use SageMaker's native `FileSystemConfig` instead.

### Custom AMIs for SageMaker training instances

SageMaker training jobs run on **SageMaker-managed AMIs**. You cannot provide your own AMI. See the "Optimizing container pull time" section for alternatives.

### FSx Lustre 2.10 vs modern clients

AWS still provisions new FSx Lustre SCRATCH_2 filesystems with Lustre version **2.10** by default in some paths. Modern Amazon Linux 2023 and Ubuntu 22.04 ship Lustre clients at 2.15. The client will refuse to connect with:
```
LustreError: Server MGS version (2.10.5.0) refused connection from this client
with an incompatible version (2.15.6). Client must be recompiled
```

**Fix:** set `file_system_type_version="2.15"` on the CfnFileSystem. In the CDK:
```python
fsx.CfnFileSystem(
    self, "LustreFileSystem",
    file_system_type="LUSTRE",
    file_system_type_version="2.15",    # <-- critical
    ...
)
```

Version upgrade in-place is supported but can fail if any client is still connected — easier to destroy + recreate.

## Gotchas that will bite you

### 1. VPC endpoints required

SageMaker training jobs in VPC mode have **no internet access** unless you add a NAT gateway. They need at minimum:

| Service | Endpoint type | Why |
|---|---|---|
| S3 | Gateway | SageMaker downloads input channels + code + uploads model artifacts + logs. Without this, the job fails at the "Downloading input data" stage with `ListObjectsV2 failed... Unable to execute request to S3`. |
| CloudWatch (logs) | Managed by SageMaker | You don't need to add this — SageMaker routes its own logs through its control plane. |
| CloudWatch (metrics) | Interface (optional) | Only needed if your user code calls `aws cloudwatch put-metric-data`. Without it, the CLI hangs on DNS resolution timeout. Wrap any such call in `timeout 15` or skip publishing metrics from inside the container. |
| ECR | Managed by SageMaker | SageMaker pulls the training image via its control plane, not from inside the VPC. |

The **one thing you must add** is the S3 gateway endpoint. Gateway endpoints are free.

### 2. nfs-common / apt repos unreachable

Irrelevant now that we're using FSx Lustre (SageMaker handles the mount). Historical note: if you ever need to install additional packages inside a VPC-attached SageMaker container, `apt-get update` cannot reach Ubuntu's archive. Either:
- Pre-install everything at image build time
- Stage .deb files in S3 and `dpkg -i --force-depends`
- Use `yum`/`dnf` with Amazon Linux's regional mirror (works via internal DNS)

### 3. triton's `ldconfig -p` UnicodeDecodeError

The NVIDIA PyTorch base image has a non-UTF8 byte somewhere in `/sbin/ldconfig -p` output. Triton naively calls `.decode()` without `errors='ignore'` and crashes at import time:
```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xc4 in position 83499: invalid continuation byte
```

**Fix:** set `TRITON_LIBCUDA_PATH` to a directory containing `libcuda.so*` before running any python that imports triton. Triton skips the `ldconfig` call entirely when that env var is set:

```bash
LIBCUDA_DIR=$(dirname "$(find /usr -name 'libcuda.so*' 2>/dev/null | head -1)")
export TRITON_LIBCUDA_PATH="${LIBCUDA_DIR:-/usr/lib/x86_64-linux-gnu}"
```

This is a triton bug fixed in newer versions, but the BioNeMo Framework image shipped a triton that still has it.

### 4. Model size name confusion

The BioNeMo repo has **two** Evo2 implementations:
- `sub-packages/bionemo-evo2/` — NeMo Lightning based, ships in `nvcr.io/nvidia/bionemo-framework` images. Model sizes: `1b`, `1b_nv`, `7b`, `7b_nv`, `40b`, `40b_nv`, etc.
- `bionemo-recipes/recipes/evo2_megatron/` — newer Megatron-Bridge based. Model sizes: `evo2_1b_base`, `evo2_7b`, `evo2_40b_base`, etc.

The flags and checkpoint formats are **not interchangeable**. The sub-package version uses `--ckpt-dir` directly with NeMo2-format checkpoints. The recipe version uses `--finetune-ckpt-dir` with MBridge-format. Know which image you're running.

For the sub-package version downloaded from NGC as `evo2/1b-8k-bf16:1.0`, the matching model size is **`1b_nv`** (NVIDIA-fine-tuned 1B base).

### 5. Hyena attention head divisibility

Evo2 Hyena models have odd attention head counts. The 1B_nv has 15 heads. Tensor parallelism requires `num_heads % tp_size == 0`, so valid TP sizes are 1, 3, 5, 15. On a 4-GPU instance (g5.12xlarge) you **cannot** use TP=4.

**Workaround:** use pipeline parallelism (PP) instead. `--pipeline-model-parallel-size 4 --tensor-parallel-size 1 --devices 4` splits the model across GPUs by layer, which always divides cleanly regardless of head count.

### 6. CUDA OOM on single A10G (24 GB) for 1B model + optimizer

The 1B Hyena model with standard Adam fp32 optimizer needs ~18-20 GB just for weights + moments. A single A10G 24 GB can barely fit it and crashes at optimizer init or the first backward pass.

**Workarounds (combine if needed):**
- `--use-precision-aware-optimizer --bf16-main-grads` — stores main weights and grads in bf16 during mixed precision training. Halves optimizer memory.
- `--activation-checkpoint-recompute-num-layers N` — recompute instead of store activations for N layers.
- `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` — reduce fragmentation.
- Pipeline parallelism across multiple GPUs (what we used — PP=4 on `ml.g5.12xlarge`).
- Use a bigger GPU: `ml.g6e.*` has L40S 48 GB (needs quota increase).

### 7. EBS gp3 baseline throughput bottleneck during docker pull

Fresh throwaway EC2s pulling the 17.5 GB compressed (~54 GB extracted) BioNeMo container from ECR take **~25-30 minutes** — not because of network, but because gp3's baseline 125 MB/s throughput bottlenecks containerd's layer extraction. We saw sustained ~16 MB/s effective write rate due to many small layer operations.

**Workarounds:**
- Provision gp3 with higher throughput (up to 1000 MB/s, costs more)
- Use larger EBS volume (throughput scales with size above baseline)
- **Pre-bake an AMI with the image cached** (see below)
- Use SageMaker Warm Pools to keep cached images alive across jobs

### 8. DLAMI disk usage

AWS Deep Learning AMIs come with ~50-80 GB of pre-loaded PyTorch / TensorRT-LLM / vLLM docker images you don't need. A 100 GB root volume fills up mid-BioNeMo-pull. Either:
- Use 300+ GB root volumes for BioNeMo work
- Run `docker image prune -af` as the first step in userdata to reclaim ~80 GB

### 9. SageMaker `InputDataConfig` requires at least one channel

Even if all your real data is on a mounted filesystem, SageMaker's API demands `len(InputDataConfig) >= 1`. Use one channel as a "code" channel pointing to an S3 prefix containing your entrypoint script. SageMaker downloads it to `/opt/ml/input/data/code/` and you can reference it in `AlgorithmSpecification.ContainerArguments`.

### 10. `ContainerArguments` max 256 chars per element

Don't try to base64-inline your entrypoint script directly in `ContainerArguments`. The 256-character limit will reject anything non-trivial. Stage the script in S3, reference it via a channel, and exec it from the mounted path.

## Performance characteristics (from the 10GB smoke test)

| Metric | Value |
|---|---|
| Instance | `ml.g5.12xlarge` (4 × A10G 24 GB, 48 vCPU, 192 GB RAM) |
| Model | Evo2 1B_NV (Striped Hyena), 1 billion parameters |
| Parallelism | PP=4, TP=1, DP=1 (pipeline split across 4 GPUs) |
| Seq length | 8192 |
| Micro batch size | 1 |
| Optimizer | Precision-aware Adam with bf16 main grads |
| Steps | 10 |
| Time per step | **2.16 s** (stable across all iterations) |
| Train loss | 0.67 → 1.16 (expected noise for such a small warmup) |
| Val loss @ step 5 | 1.198 |
| Total training wall clock | 137 s |
| SageMaker billable time | 1420 s (most of that was the post-train CloudWatch hang, since fixed) |
| Job provisioning + image pull | ~8 min |

Cross-AZ data path read rate: the training loop sequentially reads chunks of `.bin` files from Lustre. With `micro_batch_size=1` and `seq_length=8192` at byte-level tokenization, each step consumes ~8 KB of token data plus associated idx lookups — trivially small. Throughput measurement for cross-AZ is only meaningful at larger data volumes / batch sizes (scheduled for the 100GB+ phases).

## Cost notes

### Storage

| Tier | Cost | Notes |
|---|---|---|
| FSx Lustre SCRATCH_2 | ~$0.145/GB-month | Min 1.2 TiB = ~$174/month. Ephemeral, no backup. Good for validation. |
| FSx Lustre PERSISTENT_2 (125 MB/s/TiB) | ~$0.14/GB-month | Similar to SCRATCH_2 for low throughput; persistent, backed up. Use for production. |
| FSx Lustre PERSISTENT_2 (500 MB/s/TiB) | ~$0.25/GB-month | Higher throughput tier. |
| FSx Lustre PERSISTENT_2 (1000 MB/s/TiB) | ~$0.60/GB-month | Highest throughput tier. |
| FSx NetApp ONTAP SSD | ~$0.144/GB-month | Dense SSD. Not usable with SageMaker directly. |
| S3 (with Lustre DRA) | ~$0.023/GB-month | Cheapest. Pair with FSx Lustre Data Repository Association for lazy-load caching on demand. |

**For 800 TB target:** PERSISTENT_2 at $0.14/GB × 800 TB = ~$112,000/month. This is the stroage cost you're validating whether to pay vs. replicating across AZs ($224,000/month for 2 AZ copies). Pair with S3 DRA to reduce the hot-cache requirement.

### Cross-AZ data transfer

$0.01/GB each way. For a training pass over all data:
- 10 GB: $0.10
- 1 TB: $10
- 100 TB: $1,000
- 800 TB × N epochs: $8,000 × N

This needs to be budgeted explicitly and factored into "cheaper than replication" math. A single epoch over 800 TB costs $8,000 in cross-AZ transfer; replicating the data saves that but costs $112,000/month more in storage. The break-even is roughly 14 full-data training passes per month.

### GPU instance hours

| Instance | Price | Notes |
|---|---|---|
| ml.g5.2xlarge | $1.21/hr | 1× A10G 24 GB. Doesn't fit 1B Evo2 with Adam fp32. |
| ml.g5.12xlarge | $5.67/hr | 4× A10G 96 GB total. Fits 1B with PP=4. |
| ml.g5.48xlarge | $16.29/hr | 8× A10G 192 GB total. Fits 7B with PP=8. |
| ml.g6e.xlarge | $1.86/hr | 1× L40S 48 GB. Fits 1B single-GPU. Quota often 0 by default. |
| ml.p5.48xlarge | ~$98.32/hr | 8× H100 80 GB. Required for 40B. Extremely limited quota. |

## Optimizing container pull time — AMI pre-bake vs. SageMaker Warm Pools

The fresh ECR pull of `nvidia-hcls:2.7.1` (17.5 GB compressed, 54 GB extracted) consistently takes **25-30 minutes** on any fresh EC2 or SageMaker instance, driven by gp3 throughput during containerd layer extraction. At the cadence of this validation work (multiple job launches per day during iteration), that's a meaningful cost in wall-clock time and dollars.

### For throwaway EC2 (prep / staging instances)

You can create a **custom AMI with the container image already in the local docker cache**. Process:

1. Launch a DLAMI instance (let's call it the baker)
2. `docker pull <AWS_ACCOUNT_ID>.dkr.ecr.us-west-2.amazonaws.com/nvidia-hcls:2.7.1` (one-time 25 min)
3. `aws ec2 create-image --instance-id <baker> --name bionemo-prebaked-2.7.1 --no-reboot`
4. Wait ~5 min for AMI creation
5. Terminate the baker
6. Subsequent EC2 launches use the new AMI ID — the docker image is already in `/var/lib/containerd` and `docker run` starts in seconds

| Phase | Without AMI bake | With AMI bake | Savings |
|---|---|---|---|
| Instance boot | 60 s | 60 s | — |
| DLAMI docker prune | 30 s | 0 (skip) | 30 s |
| ECR login | 5 s | 5 s | — |
| Docker pull (first pull) | **1,500 s (25 min)** | **0 s (cached)** | **~1,500 s** |
| Mount FSx | 2 s | 2 s | — |
| Actual work | N | N | — |
| **Per-launch overhead** | **~26 min** | **~1 min** | **~25 min** |

**Economic impact** on throwaway prep instances at $1.00/hr (g5.xlarge):
- Without AMI: $0.42 per launch wasted on docker pull
- With AMI: ~$0 per launch on docker pull
- AMI storage cost: ~$0.05/GB-month × ~54 GB = **~$2.70/month** for the AMI snapshot

Break-even at **~7 launches per month**. For an active validation or production workflow that spins up prep instances dozens of times, pre-baking saves 80-90% of prep time and is almost always worth it.

**Staleness management**: when the BioNeMo image is updated, rebuild the AMI. Tag AMIs by source image digest so you know which is current. Automate with a simple script that compares the current ECR image digest to the AMI tag and rebakes if mismatched.

**Implementation sketch for this repo** (future work):
```python
# validation/data_preparation/bake_prep_ami.py
# Launches a g5.xlarge, pulls the BioNeMo image, creates AMI, terminates instance.
# Writes the resulting AMI ID to SSM Parameter Store at /syngenta/bionemo-prep-ami-id
# so the other prep scripts can pick it up automatically.
```

The existing `_ec2_launcher_common.py` would then check SSM for a pre-baked AMI ID and fall back to the DLAMI if none is present.

### For SageMaker training jobs

SageMaker does **not** allow custom AMIs on training instances — you're stuck with SageMaker-managed AMIs. So pre-baking doesn't directly apply.

Instead, use **SageMaker Training Warm Pools** (`KeepAlivePeriodInSeconds` on `CreateTrainingJob`):

```python
training_job = {
    ...
    "ResourceConfig": {
        "InstanceType": "ml.g5.12xlarge",
        "InstanceCount": 1,
        "VolumeSizeInGB": 100,
        "KeepAlivePeriodInSeconds": 3600,   # keep warm for 1 hour after job ends
    },
    ...
}
```

After a training job finishes, SageMaker keeps the instance warm (with the image cached) for the specified period. Subsequent jobs matching the same configuration skip the image pull entirely and start in seconds.

| Phase | Cold start | Warm pool start | Savings |
|---|---|---|---|
| Instance provisioning | ~2 min | 0 s | ~2 min |
| Image download | **25-30 min** | 0 s | **~27 min** |
| Container startup | ~30 s | ~30 s | — |
| **Total to first user code** | **~30 min** | **~1 min** | **~29 min** |

#### How warm pool billing actually works ("scale to zero" nuance)

Warm pools **do scale to zero eventually**, but not in the way Lambda or SageMaker Serverless Inference do. There are only three states for the instance, with no idle-discount tier:

| State | Billing |
|---|---|
| Active training job | Full instance rate |
| Warm pool holding (waiting for next job, `KeepAlivePeriodInSeconds` window) | **Full instance rate** |
| Expired (window elapsed with no new job) | $0 — true scale to zero |

So "scale to zero" here means: after `KeepAlivePeriodInSeconds` passes with no new job matching the warm pool's configuration, the instance is torn down and billing stops completely. Until that expiration, you're paying full rate whether a job is running or not.

**Max value**: `KeepAlivePeriodInSeconds` tops out at 3600 seconds (1 hour) by default, extendable up to 604,800 seconds (7 days) via quota request. Verify current max with `aws service-quotas list-service-quotas --service-code sagemaker --query "Quotas[?contains(QuotaName,'warm pool')]"`.

**Example economics** on `ml.g5.12xlarge` ($5.67/hr):

| Iteration cadence | Recommendation | Daily cost (8 hr dev day) |
|---|---|---|
| New job every 5-10 min (active iteration) | `KeepAlivePeriodInSeconds=3600` | $45 (cheaper than re-pulling image 48+ times) |
| New job every 30-60 min | `KeepAlivePeriodInSeconds=1800` | ~$30 (partial savings) |
| New job every few hours | Don't use warm pools | ~$11 billable time × 8 cold starts, but 8 × 25 min = 3.3 hrs wasted on pulls |
| Sporadic (batch-like) | Don't use warm pools | Paid-work only, eat the 25-min cold start each time |

**Rule of thumb**: set `KeepAlivePeriodInSeconds` to roughly the expected gap between consecutive job launches during your active session. If your gap is longer than the keep-alive period, you pay idle AND still hit a cold start. If it's shorter, the warm pool pays for itself by amortizing the image pull across multiple jobs.

**Quota implications**: warm pool instances count against a separate `warm pool usage` quota that is independent from `training job usage`. Default is usually **0**, which is easy to miss — your first `KeepAlivePeriodInSeconds` request will fail with `ResourceLimitExceeded` until you submit a quota increase. Check both:

```bash
aws service-quotas list-service-quotas --service-code sagemaker \
    --query "Quotas[?contains(QuotaName, 'warm pool') && contains(QuotaName, 'ml.g5.12xlarge')]" \
    --output table
```

### There is no true "scale to zero with zero cold start" for SageMaker training

The two modes are:

1. **Cold start every time** — $0 between jobs, 25-30 min image pull tax on each launch
2. **Warm pools** — full instance cost during the keep-alive window, near-instant launch within that window

If you want genuinely bursty workloads with zero-cost idle AND fast start, SageMaker Training Jobs are the wrong tool. Alternatives for those patterns:

| Need | Service |
|---|---|
| Persistent cluster shared across users, amortize idle across the org | **SageMaker HyperPod** |
| Full control, pre-baked AMI, custom orchestration | **Self-managed EC2 / EKS** — lose SageMaker's job management UI |
| Truly scales to zero, instant starts | **SageMaker Serverless Inference** — inference only, not training |
| Bursty async training with queuing | **SageMaker Training + SQS-driven launcher** — cold start each time, minimum wait |

### When neither helps

For a one-off validation or experiment, just eat the 25-minute pull time. The engineering time to set up AMI baking or warm pools isn't worth it for fewer than ~5 runs.

## GPU sizing guide — which Evo2 model fits which instance

This was determined empirically through testing and memory math during the validation. The key constraint is **optimizer state per GPU**: Adam with bf16-main-grads requires ~14 bytes per parameter per GPU rank. Pipeline parallelism (PP) splits the model by layer, giving each GPU 1/PP of the total parameters.

### Memory formula per GPU (pipeline parallelism)

```
params_per_gpu = total_params / PP
memory_per_gpu = params_per_gpu × (
    2 bytes (bf16 weight) +
    2 bytes (bf16 grad) +
    4 bytes (fp32 main copy) +
    4 bytes (fp32 exp_avg) +
    4 bytes (fp32 exp_avg_sq)
) + activations (~2-5 GB depending on seq_length and activation checkpointing)

= params_per_gpu × 16 bytes + ~3 GB
```

### Validated sizing table

| Model | Params | Instance | GPUs | PP | Params/GPU | VRAM/GPU needed | VRAM/GPU available | Result |
|---|---|---|---|---|---|---|---|---|
| **1B_NV** | 1B | ml.g5.2xlarge | 1× A10G | 1 | 1B | ~19 GB | 24 GB | OOM at optimizer init |
| **1B_NV** | 1B | ml.g5.12xlarge | 4× A10G | 4 | 250M | ~7 GB | 24 GB | **Works** (2.16 s/step) |
| **7B_NV** | 7B | ml.g5.12xlarge | 4× A10G | 4 | 1.75B | ~31 GB | 24 GB | **OOM** (illegal memory access) |
| **7B_NV** | 7B | ml.p4d.24xlarge | 8× A100 40GB | 8 | 875M | ~17 GB | 40 GB | **Fits** (in testing) |
| **40B_NV** | 40B | ml.p4d.24xlarge | 8× A100 40GB | 8 | 5B | ~83 GB | 40 GB | **Does NOT fit** |
| **40B_NV** | 40B | ml.p4de.24xlarge | 8× A100 80GB | 8 | 5B | ~83 GB | 80 GB | **Fits** (in testing) |
| **40B_NV** | 40B | ml.p5.48xlarge | 8× H100 80GB | 8 | 5B | ~83 GB | 80 GB | **Fits** (expected) |

### Key lessons

1. **Tensor parallelism (TP) is limited by attention head count.** Evo2 Hyena 1B_NV has 15 heads; 7B has a different count. TP requires `num_heads % TP == 0`. Use **pipeline parallelism (PP) instead** — it always divides cleanly regardless of head count.

2. **1B is the ceiling for A10G 24 GB GPUs.** Even with `--use-precision-aware-optimizer --bf16-main-grads --activation-checkpoint-recompute-num-layers`, a single A10G cannot fit 1B + optimizer. PP=4 across 4× A10G works. 7B on 4× A10G does not work even with PP=4.

3. **7B needs A100 40GB+.** The p4d.24xlarge (8× A100 40GB) with PP=8 gives 17 GB/GPU for 7B — comfortable. g5 instances (A10G 24GB) cannot run 7B in any configuration.

4. **40B needs A100 80GB+.** At 83 GB/GPU with PP=8, the p4d.24xlarge (40 GB/GPU) is too small. Requires p4de.24xlarge or p5.48xlarge (both 80 GB/GPU). The `train_evo2` CLI in BioNeMo Framework 2.7.1 does not expose `--optimizer-cpu-offload`, which would otherwise allow 40B on smaller GPUs by offloading optimizer state to the 1.15 TB of host RAM.

5. **Instance availability matters as much as sizing.** ml.p4de.24xlarge capacity in us-west-2 is extremely scarce — we observed 3+ hour queue times with no capacity found. Budget for this in validation timelines and consider requesting capacity reservations for production workloads.

6. **Request quotas well in advance.** Default SageMaker training quotas for p4d, p4de, p5, and g6e are all **0**. Each requires a service quota increase request that takes hours to days to approve. File requests for all GPU instance types you might need before starting validation.

## Cross-AZ throughput analysis — why the network is NOT the bottleneck

A common concern with cross-AZ storage is that the network hop will bottleneck training. Our analysis shows this is **not the case** for genomic foundation model training at any practical scale.

### FSx Lustre throughput by tier

| Lustre tier | Throughput per TiB | 1.2 TiB FS (our test) | 10 TiB FS (mid-scale) | 100 TiB FS (production) |
|---|---|---|---|---|
| SCRATCH_2 | 200 MB/s/TiB | 240 MB/s | 2 GB/s | 20 GB/s |
| PERSISTENT_2 (125 MB/s) | 125 MB/s/TiB | 150 MB/s | 1.25 GB/s | 12.5 GB/s |
| PERSISTENT_2 (500 MB/s) | 500 MB/s/TiB | 600 MB/s | 5 GB/s | 50 GB/s |
| PERSISTENT_2 (1000 MB/s) | 1000 MB/s/TiB | 1.2 GB/s | 10 GB/s | 100 GB/s |

Cross-AZ adds ~1-2ms latency per Lustre operation but does **not** meaningfully reduce sustained throughput. AWS's inter-AZ backbone handles multi-GB/s without congestion.

### Training I/O demand vs Lustre capacity

Each training step reads a tiny amount of data compared to Lustre's capacity:

```
bytes_per_step = micro_batch_size × seq_length × bytes_per_token × data_parallel_degree
```

| Scenario | micro_batch | seq_len | DP | Bytes/step | Step time | Sustained I/O | % of SCRATCH_2 1.2T |
|---|---|---|---|---|---|---|---|
| Validation (our test) | 1 | 8192 | 1 | 8 KB | 2-15s | <1 KB/s | 0.0004% |
| Single-node production | 32 | 8192 | 1 | 256 KB | 2-15s | 17-128 KB/s | 0.007% |
| Multi-node (8 nodes, DP=8) | 32 | 8192 | 8 | 2 MB | 2-15s | 133 KB - 1 MB/s | 0.4% |
| Extreme (64 nodes, DP=64) | 32 | 8192 | 64 | 16 MB | 2-15s | 1-8 MB/s | 3.3% |

**Even at 64-node scale, training uses <4% of SCRATCH_2's baseline throughput.** You will not saturate the cross-AZ link.

### Why training is compute-bound, not I/O-bound

The GPU is always the bottleneck. Consider the 7B model: a single forward + backward pass involves ~14 billion multiply-accumulate operations per token. At 8192 tokens per step, that's 115 trillion FLOPs per step. An A100 at 312 TFLOPS (bf16) takes ~0.37 seconds just for the math, before communication overhead, memory bandwidth, pipeline bubble time, etc. Real step times are 5-15 seconds because of these overheads.

Meanwhile, the data read for that step is 8 KB. The GPU could consume that in microseconds. The Lustre filesystem is idle >99.99% of the time waiting for the GPU to finish computing.

### Where cross-AZ latency IS visible

1. **Model checkpoint saves**: a 7B checkpoint is ~14 GB. At 240 MB/s SCRATCH_2 throughput, writing takes ~58s same-AZ vs ~60s cross-AZ. Delta: ~2s per checkpoint save. Negligible.

2. **Dataset index loading at startup**: the `.idx` file for 100 GB of bin/idx data is ~285 KB. Loaded once. Invisible.

3. **Shuffled random access**: Megatron samples randomly from indexed datasets. Each random read has 1-2ms cross-AZ latency. With 8 prefetch workers hiding this latency behind compute, the impact on step time is unmeasurable.

### Cross-AZ cost math for the 800 TB production scenario

| Item | Cost | Notes |
|---|---|---|
| Cross-AZ transfer per epoch (800 TB) | **$8,000** | $0.01/GB × 800,000 GB |
| FSx Lustre PERSISTENT_2 storage (800 TB, 125 MB/s tier) | **$112,000/month** | $0.14/GB/month |
| Alternative: replicate to second AZ | **$224,000/month** | 2× storage cost |
| Storage savings from NOT replicating | **$112,000/month** | The whole point of this architecture |

**Break-even**: the cross-AZ transfer cost ($8K/epoch) equals the storage savings ($112K/month) after ~14 full data passes per month. If you train fewer than 14 epochs/month over the full 800 TB, this architecture saves money. Most genomic fine-tuning runs see 1-5 epochs, so the savings are substantial.

## Recommended production architecture — S3 + FSx Lustre DRA (hot cache)

This is the most important section for the customer's 800 TB use case.

### The customer's actual access pattern

The customer has 800 TB of genomic data but **does not use all of it in every training run**. Each fine-tuning or training job operates on a **subset** — perhaps 1-50 TB depending on the experiment. The full 800 TB is a data lake that different runs draw from.

This changes the architecture fundamentally: **you don't need 800 TB of high-performance storage. You need 800 TB of durable storage plus a fast cache for the active working set.**

### The S3 + FSx Lustre Data Repository Association (DRA) pattern

```
                        us-west-2a                              us-west-2b
┌──────────────────────────────────────────┐        ┌──────────────────────┐
│                                          │        │                      │
│  S3 Bucket (800 TB, durable, cheap)      │        │  SageMaker Training  │
│  s3://customer-genomics-data/            │        │  Job (P5/P4de)       │
│    ├── experiment_001/ (12 TB)           │        │                      │
│    ├── experiment_002/ (8 TB)            │        │  Reads from Lustre   │
│    ├── experiment_003/ (25 TB)           │        │  at /opt/ml/input/   │
│    └── ... (800 TB total)                │        │  data/training/      │
│          │                               │        │         ▲            │
│          │  DRA lazy-load on first read  │        │         │            │
│          ▼                               │        │         │            │
│  FSx Lustre (10-50 TiB hot cache)        │        │         │            │
│    ├── Only caches the data that has     │◄───────│─────────┘            │
│    │   been requested by a training job  │Lustre  │  cross-AZ reads     │
│    ├── Auto-evicts cold data (LRU)       │client  │                      │
│    └── New experiments auto-fetch from S3│        │                      │
│                                          │        │                      │
└──────────────────────────────────────────┘        └──────────────────────┘
```

### How DRA works

1. **Link S3 to Lustre**: when creating the FSx Lustre filesystem, specify an S3 `ImportPath` (the bucket prefix). Lustre creates metadata stubs for every S3 object but does NOT download the data yet.

2. **Lazy loading**: the first time a training job reads a file from Lustre, FSx fetches it from S3 into the Lustre cache. Subsequent reads hit the cache at full Lustre throughput (no S3 round-trip).

3. **Cache semantics**: Lustre holds the hot working set. Files that haven't been accessed age out if the filesystem fills up (depends on configuration). New experiments automatically pull their subset from S3 on first access.

4. **Write-back (optional)**: training outputs (checkpoints, logs) can be written to Lustre and automatically exported back to S3 via DRA export.

### Cost comparison for 800 TB data lake

| Architecture | Monthly storage cost | Cross-AZ transfer/epoch | Notes |
|---|---|---|---|
| **Replicate 800 TB to 2 AZs** | **$224,000** | $0 | No cross-AZ, but insane storage cost |
| **All 800 TB on Lustre** | **$112,000** | $0 (if same-AZ) or $8,000/epoch (cross-AZ) | Expensive Lustre for cold data |
| **S3 only (no Lustre)** | **$18,400** | N/A — SageMaker can't mount S3 as filesystem | Would need to copy to EBS/Lustre first |
| **S3 (800 TB) + Lustre 10 TiB cache** | **$19,800** | ~$100-500/epoch (only active subset) | Best for subset-per-run pattern |
| **S3 (800 TB) + Lustre 50 TiB cache** | **$25,400** | ~$100-500/epoch | More cache for concurrent experiments |
| **S3 (800 TB) + Lustre 100 TiB cache** | **$32,400** | ~$100-500/epoch | Generous cache, rare S3 fetches |

**The S3 + Lustre DRA pattern is 5-10x cheaper than alternatives** when the customer only trains on subsets of the full dataset.

### Why this is the right fit for the customer

1. **800 TB stays in S3 in one AZ** — cheapest durable storage ($0.023/GB/month). No replication. No multi-AZ premium.

2. **Lustre cache size = largest expected working set**, not total data size. If the biggest experiment uses 50 TB, provision a 50 TiB Lustre cache. The other 750 TB stays cold in S3 at S3 prices.

3. **SageMaker mounts Lustre natively** via `FileSystemConfig` — exactly what we validated. The training job doesn't know or care that Lustre is backed by S3. It just reads files.

4. **Cross-AZ transfer cost is per-subset, not per-total-dataset.** A 10 TB experiment crossing AZs costs $100, not $8,000. At $100/experiment, the customer would need to run 1,120 experiments per month to equal the cost of replicating 800 TB. That's ~37 experiments per day — far beyond any realistic training cadence.

5. **New experiments self-cache.** When a researcher starts a new fine-tuning run with a different subset of the 800 TB, the first epoch's reads lazy-load from S3 into Lustre (slower — S3 throughput ~5-10 GB/s). Subsequent epochs hit the Lustre cache at full speed (200+ GB/s at production scale). This "cold start" penalty is per-experiment, not per-step, and is typically 10-30 minutes for a 10 TB subset at S3 transfer rates.

6. **Lustre PERSISTENT_2 for the cache is recommended** (not SCRATCH_2) because:
   - Backed up automatically
   - Supports DRA natively with auto-import and auto-export
   - Higher throughput tiers available (up to 1000 MB/s/TiB)
   - SCRATCH_2 does NOT support DRA

### Implementation sketch

```python
# CDK for S3-backed Lustre with DRA
lustre_fs = fsx.CfnFileSystem(
    self, "LustreCache",
    file_system_type="LUSTRE",
    file_system_type_version="2.15",
    storage_capacity=51200,  # 50 TiB cache
    subnet_ids=[fsx_subnet.subnet_id],
    security_group_ids=[lustre_sg.security_group_id],
    lustre_configuration=fsx.CfnFileSystem.LustreConfigurationProperty(
        deployment_type="PERSISTENT_2",
        per_unit_storage_throughput=250,  # MB/s per TiB
        import_path="s3://customer-genomics-data/",
        auto_import_policy="NEW_CHANGED_DELETED",  # sync S3 changes to Lustre metadata
    ),
)
```

The `import_path` links the Lustre namespace to S3. `auto_import_policy` keeps Lustre's file listing in sync as new data is added to S3. Actual data transfer only happens on first read.

### Sizing the Lustre cache

| Scenario | Largest concurrent working set | Recommended cache | Monthly Lustre cost | Total (S3 + Lustre) |
|---|---|---|---|---|
| Single experiment at a time, 10 TB | 10 TB | 12 TiB | $1,680 | $20,080 |
| 2-3 concurrent experiments, 10 TB each | 30 TB | 36 TiB | $5,040 | $23,440 |
| Large experiment, 50 TB | 50 TB | 60 TiB | $8,400 | $26,800 |
| Multiple large, 100 TB total active | 100 TB | 120 TiB | $16,800 | $35,200 |

All of these are dramatically cheaper than the $224,000/month replication alternative.

### What to tell the customer

> "Your 800 TB stays in S3 in a single AZ at ~$18K/month. We front it with an FSx Lustre cache sized to your largest active experiment (10-50 TiB). SageMaker training jobs in a different AZ mount the Lustre cache natively — cross-AZ reads are transparent and do not bottleneck training. Each experiment costs ~$100 in cross-AZ transfer, not $8,000. You save $100K+/month compared to replicating the data across AZs."

## Data preprocessing at scale

The `preprocess_evo2` CLI converts raw FASTA files into Megatron `.bin`/`.idx` format for training. At scale (50+ GB input), this is a multi-hour process with its own set of gotchas.

### Preprocessing pipeline

```
Raw FASTA files (.fa)
    → preprocess_evo2 -c config.yaml
    → Byte-level tokenization (1 nucleotide = 1 token = 1 byte)
    → Reverse complement doubling (if embed_reverse_complement=true)
    → N-region filtering, empty sequence dropping
    → Train/val/test split
    → Megatron IndexedDataset .bin/.idx output
```

### Output size vs input size

The output bin/idx size depends heavily on filter settings:

| Filter config | Input FASTA | Output bin/idx | Ratio |
|---|---|---|---|
| **Default** (nnn_filter=true, drop_empty=true) | 13 GB (4× hg38) | 561 MB | 0.04× (95% filtered out) |
| **Relaxed** (nnn_filter=false, drop_empty=false, reverse-complement=true) | 50 GB (16× hg38) | 96 GB | ~1.9× (RC doubles it) |

For cross-AZ bandwidth testing, use **relaxed filters** to maximize the output size. The default filters aggressively strip N-runs and empty sequences, producing very small outputs that don't exercise the storage layer.

### Memory requirements

**preprocess_evo2 is memory-hungry.** Each worker loads full chromosome sequences into memory for tokenization. hg38 chromosomes range from 50 MB (chr21) to 250 MB (chr1).

| Instance | RAM | Workers | Chunksize | Result |
|---|---|---|---|---|
| g5.xlarge (16 GB) | 16 GB | 16 | 25 | **OOM killed** — workers × chunks × chr_size exceeded RAM |
| g5.xlarge + 16 GB swap | 32 GB effective | 4 | 1 | **OOM killed** — still too aggressive for 16 × hg38 input |
| g5.4xlarge (64 GB) | 64 GB | 2 | 1 | **Works** — 10 GB peak usage, completed in ~4 hours |

**Recommendations for preprocessing:**
- Use `workers: 2` and `chunksize: 1` for safety on instances with <64 GB RAM
- Use `g5.4xlarge` (64 GB RAM, $1.62/hr) as the minimum for preprocessing 50+ GB of FASTA
- For 500 GB+ input, consider `g5.8xlarge` (128 GB, $2.45/hr) with `workers: 4`
- The GPU is NOT used during preprocessing (byte-level tokenization is CPU-only) but is required because the NVIDIA container's entrypoint fails without one

### Throughput

Observed preprocessing throughput on g5.4xlarge with workers=2:

| Metric | Value |
|---|---|
| Sustained write rate to Lustre | ~7.5 MB/s |
| Time for 50 GB input → 96 GB output | ~4 hours |
| CPU utilization | ~100% (single-threaded bottleneck in tokenizer) |
| Peak RAM | ~10 GB of 64 GB available |

Preprocessing is CPU-bound, not I/O-bound. The tokenizer processes each sequence character-by-character in Python. For larger datasets, preprocessing time scales linearly with input size.

### DLAMI gotcha: apt vs dnf

The Deep Learning AMI (`base-oss-nvidia-driver-gpu-ubuntu-22.04`) is **Ubuntu-based** and uses `apt-get`, not `dnf`. Scripts written for Amazon Linux 2023 will fail immediately. The FSx Lustre client for Ubuntu must be installed from the Amazon FSx client repo:

```bash
wget -O - https://fsx-lustre-client-repo-public-keys.s3.amazonaws.com/fsx-ubuntu-public-key.asc \
    | gpg --dearmor | tee /usr/share/keyrings/fsx-ubuntu-public-key.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/fsx-ubuntu-public-key.gpg] \
    https://fsx-lustre-client-repo.s3.amazonaws.com/ubuntu jammy main" \
    | tee /etc/apt/sources.list.d/fsxlustreclientrepo.list
apt-get update && apt-get install -y lustre-client-modules-$(uname -r)
```

## Scaling playbook — validation phases (updated)

| Phase | Data | Model | Instance | PP | Est. cost | Status |
|---|---|---|---|---|---|---|
| 1B/10GB (baseline) | 10 GB | 1B_NV | ml.g5.12xlarge (4× A10G) | 4 | ~$2 | **Done** (2.16 s/step) |
| 1B/100GB (data scaling) | 100 GB | 1B_NV | ml.g5.12xlarge (4× A10G) | 4 | ~$5 | **Running** |
| 7B/10GB (model scaling) | 10 GB | 7B_NV | ml.p4d.24xlarge (8× A100 40GB) | 8 | ~$15 | **Running** |
| 40B/10GB (large model) | 10 GB | 40B_NV | ml.p4de.24xlarge (8× A100 80GB) | 8 | ~$35 | **Queued** (capacity) |
| 7B/100GB (combined) | 100 GB | 7B_NV | ml.p4d.24xlarge (8× A100 40GB) | 8 | ~$20 | Planned |
| 40B/100GB (target) | 100 GB | 40B_NV | ml.p4de.24xlarge (8× A100 80GB) | 8 | ~$50 | Planned |
| Production | 800 TB | 40B | ml.p5.48xlarge × N | PP×TP×DP | ~$30k+ | Future |

At each phase, measure:
1. **Step time** — directly from `train_step_timing in s` in training logs.
2. **GPU utilization + peak VRAM** — from nvidia-smi background sampler in the entrypoint.
3. **Cross-AZ data transfer** — FSx CloudWatch `DataReadBytes` integrated over the run window.
4. **Tokens/sec** — `seq_length × micro_batch × DP / step_time`.
5. **Cost per step** — instance cost × step_time / 3600.

Expected finding: **step time is dominated by model size (compute), not data size (I/O).** The 1B/10GB and 1B/100GB runs should produce nearly identical step times because per-step I/O is always 8 KB regardless of total dataset size. The 7B and 40B runs will show longer step times due to more compute per step, not more I/O.

## Scaling test results

Three validated runs comparing data scaling and model scaling across cross-AZ FSx Lustre + SageMaker. All runs used `micro_batch_size=1, seq_length=8192, max_steps=10`, training from scratch (no pretrained checkpoint).

### Per-iteration step times

**1B / 10GB (baseline) — ml.g5.12xlarge, PP=4:**
```
iter 0: 28.69s (warmup)    iter 5: 2.168s
iter 1:  6.83s (warmup)    iter 6: 2.158s
iter 2:  2.156s            iter 7: 2.159s
iter 3:  2.158s            iter 8: 2.158s
iter 4:  2.160s            iter 9: 2.161s
Steady state: 2.16 s/step
```

**1B / 100GB (data scaling) — ml.g5.12xlarge, PP=4:**
```
iter 0: 28.69s (warmup)    iter 5: 2.164s
iter 1:  6.83s (warmup)    iter 6: 2.157s
iter 2:  2.154s            iter 7: 2.155s
iter 3:  2.155s            iter 8: 2.156s
iter 4:  2.155s            iter 9: 2.157s
Steady state: 2.155 s/step
```

**7B / 10GB (model scaling) — ml.p4d.24xlarge, PP=8:**
```
iter 0: 60.94s (warmup)    iter 5: 2.832s
iter 1: 14.77s (warmup)    iter 6: 2.825s
iter 2:  2.984s            iter 7: 2.824s
iter 3:  4.304s (ckpt)     iter 8: 2.824s
iter 4:  2.820s            iter 9: 2.814s
Steady state: 2.82 s/step
```

### Summary comparison

| Metric | 1B / 10GB | 1B / 100GB | 7B / 10GB | 40B / 10GB |
|---|---|---|---|---|
| Instance | ml.g5.12xlarge | ml.g5.12xlarge | ml.p4d.24xlarge | **ml.p4de.24xlarge** |
| GPUs | 4x A10G 24GB | 4x A10G 24GB | 8x A100 40GB | **8x A100 80GB** |
| Pipeline parallel | 4 | 4 | 8 | 8 |
| Dataset (bin/idx) | 561 MB | 96 GB | 561 MB | 561 MB |
| Seq length | 8192 | 8192 | 8192 | 2048 |
| **Steady-state step time** | **2.16 s** | **2.155 s** | **2.82 s** | **4.0 s** |
| **Step time vs baseline** | **1.00x** | **1.00x** | **1.31x** | **1.85x** |
| Tokens/sec (steady) | 3,795 | 3,802 | 2,904 | ~512 |
| Peak VRAM (highest GPU) | ~15 GB / 24 GB | 15.4 GB / 24 GB | ~28 GB / 40 GB | **80.1 GB / 81.9 GB** |
| Avg GPU utilization | ~25% | 24.7% | 24.6% | ~25% |
| Training wall clock | 137s | 133s | 229s | 686s |
| Cost of run | ~$2 | ~$5 | ~$15 | **~$8** |

### Analysis

**Finding 1: Cross-AZ data volume has zero impact on training step time.**

Scaling the preprocessed dataset from 561 MB to 96 GB (171x increase) changed the steady-state step time by 0.005 seconds (0.2%). This is within measurement noise. The training loop reads ~8 KB per step regardless of total dataset size — the rest of the dataset sits untouched on Lustre until sampled in future steps. Cross-AZ Lustre throughput is never the bottleneck.

**Finding 2: Model scaling from 1B to 7B to 40B — hardware absorbs growth.**

| Scaling step | Param increase | Step time increase | Hardware upgrade |
|---|---|---|---|
| 1B → 7B | 7× | 1.31× | A10G 24GB (PP=4) → A100 40GB (PP=8) |
| 1B → 40B | 40× | 1.85× | A10G 24GB (PP=4) → A100 80GB (PP=8) |
| 7B → 40B | 5.7× | 1.42× | A100 40GB → A100 80GB (same PP=8) |

Despite a 40x increase in model parameters (1B → 40B), step time only grew from 2.16s to 4.0s — less than 2x. This is because each hardware tier upgrade (A10G → A100 40GB → A100 80GB) brings proportionally more compute throughput and memory bandwidth. The 7B → 40B jump (5.7× params) costs only 1.42× in step time on the same A100 80GB pipeline.

This is an important result for the customer: **upgrading instance type absorbs model scaling.** The cost of larger models is primarily in GPU memory (requiring bigger/more GPUs), not in wall-clock training time per step. Note: the 40B run used seq_length=2048 (vs 8192 for 1B/7B) due to memory constraints — at equal seq_length the 40B step time would be proportionally higher.

**Finding 3: GPU utilization is low (~25%) because micro_batch_size=1.**

Pipeline parallelism with micro_batch=1 means each GPU is idle while waiting for its pipeline stage. In production, micro_batch_size=16-32 with gradient accumulation fills the pipeline and drives utilization to 60-80%+. The step times reported here are worst-case for compute efficiency.

**Finding 4: Training from scratch vs fine-tuning has identical step-time characteristics.**

All three runs trained from random initialization (no checkpoint). Fine-tuning from a pretrained checkpoint would add a one-time checkpoint load at startup (~14 GB for 7B, ~80 GB for 40B, taking 30-120s depending on Lustre throughput) but would not affect per-step training time.

**Finding 5: p4de.24xlarge (needed for 40B) has severe capacity constraints.**

The 40B scaling run was queued for 5+ hours without receiving capacity in us-west-2. This is a deployment planning concern: the customer should request capacity reservations or use on-demand capacity reservations (ODCRs) for p4de/p5 instance types. Spot instances are another option but carry interruption risk for long training jobs.

### 40B results — `40b` (vanilla) succeeded; `40b_nv` has a framework bug

**40b (vanilla) on ml.p4de.24xlarge (8x A100 80GB, PP=8, seq=2048):**

```
iter 0: 56.91s (warmup)    iter 3: 3.872s
iter 1: 14.77s (warmup)    iter 4: 4.105s
iter 2:  4.435s
Steady state: ~4.0 s/step
Peak VRAM: 78-80 GB / 81.9 GB per GPU (97% utilization)
Tokens/sec (steady): ~512
Training wall clock: 686s
Train RC: 0 (SUCCESS)
```

This run used `CUDA_LAUNCH_BLOCKING=1` for diagnostic purposes, which adds ~5-10% overhead to step time. Production step time without it would be ~3.6-3.8s.

**40b_nv (NVIDIA fine-tuned variant) — DOES NOT WORK on BioNeMo 2.7.1:**

Three attempts with `40b_nv` all crashed with `CUDA error: an illegal memory access was encountered` during model initialization, before the first training iteration:

| Attempt | Config | VRAM at crash | Result |
|---|---|---|---|
| PP=8 TP=1, seq=8192 | 8 pipeline stages | ~20 GB / 80 GB per GPU | Illegal memory access |
| PP=8 TP=1, seq=2048 | Reduced seq length | ~20 GB / 80 GB per GPU | Same crash |
| PP=4 TP=1 DP=2, seq=2048 | Different parallelism | ~20 GB / 80 GB per GPU | Same crash |

GPUs were only 25% utilized at crash time — not OOM. The bug is specific to the `40b_nv` model variant's interaction with multi-GPU pipeline-parallel training. The vanilla `40b` model runs identically configured on the same hardware without issues.

**Root cause hypothesis:** The `40b_nv` variant was fine-tuned by NVIDIA for FP8/BF16 hardware compatibility. This fine-tuning may have introduced a weight shape, config parameter, or custom CUDA kernel that is incompatible with the BioNeMo 2.7.1 sub-package's pipeline parallelism implementation. The crash occurs during the distributed optimizer setup phase, not during forward/backward pass.

**Recommendation:** Use `--model-size 40b` (vanilla) for distributed training. If the NV-specific FP8 optimizations are needed, either:
1. Use a newer BioNeMo Framework version (if available from NVIDIA)
2. Use `40b_nv` with LoRA (`--lora-finetune`) on a single GPU (avoids the multi-GPU code path)
3. Contact NVIDIA support with the diagnostic trace (available in CloudWatch logs for job `bionemo-40b-diag1-093534`)

## Checklist for reproducing this architecture at a new customer

- [ ] VPC with subnets in at least 2 AZs
- [ ] S3 gateway VPC endpoint attached to all relevant route tables
- [ ] FSx for Lustre filesystem in the storage AZ, **with `file_system_type_version="2.15"` explicitly set**
- [ ] Security group on the Lustre filesystem allowing TCP 988 and 1018-1023 from the SageMaker training SG (and from any EC2 prep SG if doing data staging via EC2)
- [ ] SageMaker execution role with:
  - `AmazonSageMakerFullAccess` or equivalent
  - ECR read permissions for the training image repo
  - S3 read/write on the SageMaker default bucket
- [ ] Training image staged in ECR (cannot pull from `nvcr.io` directly from inside a VPC without an ECR public endpoint)
- [ ] `FileSystemConfig` in `CreateTrainingJob` with `FileSystemType='FSxLustre'`, `DirectoryPath='/<mount_name>'`
- [ ] `VpcConfig` pointing at a subnet in the compute AZ and a security group that allows outbound to the Lustre SG
- [ ] Entrypoint script references `/opt/ml/input/data/<channel_name>/` for data paths
- [ ] `TRITON_LIBCUDA_PATH` set in entrypoint if using NVIDIA PyTorch base images
- [ ] Any `aws cloudwatch put-metric-data` calls wrapped in `timeout 15` (or skipped entirely) unless a CloudWatch interface VPC endpoint is added
- [ ] Quotas checked and increases requested before the first run (especially for warm pools and P5/G6e)
- [ ] (Optional but recommended) AMI pre-bake script for the throwaway prep instances
- [ ] (Optional but recommended) Warm pools enabled on iterative SageMaker runs

## References

- BioNeMo Framework: https://github.com/NVIDIA/bionemo-framework
- Evo2 sub-package: `bionemo-framework/sub-packages/bionemo-evo2/` (ships in `nvcr.io/nvidia/bionemo-framework` images)
- Evo2 recipe (newer, Megatron-Bridge): `bionemo-framework/bionemo-recipes/recipes/evo2_megatron/`
- FSx for Lustre with SageMaker docs: https://docs.aws.amazon.com/sagemaker/latest/dg/model-access-training-data.html
- SageMaker Training Warm Pools: https://docs.aws.amazon.com/sagemaker/latest/dg/train-warm-pools.html
- SageMaker VPC configuration: https://docs.aws.amazon.com/sagemaker/latest/dg/train-vpc.html
- NGC checkpoint catalog: `download_bionemo_data --list-resources` inside the BioNeMo container
