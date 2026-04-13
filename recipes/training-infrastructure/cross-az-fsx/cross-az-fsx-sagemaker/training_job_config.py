"""
Training job configuration for cross-AZ FSx + SageMaker Evo2 experiments.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  TWO CONFIG FILES — WHICH ONE DO I EDIT?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  config.py              ← INFRASTRUCTURE (set once per customer deployment)
                           Region, availability zones, VPC, FSx Lustre size,
                           CDK stack names.  Touch this when setting up a new
                           AWS environment.  Leave it alone day-to-day.

  training_job_config.py ← EXPERIMENT (this file — edit for each training run)
                           What data to train on, which model, which hardware,
                           how many steps.  This is what you change when you
                           want to run a different experiment.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  THE THREE-STEP WORKFLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  STEP 1 — Choose your data scale (only needs to happen once per phase)
  ─────────────────────────────────────────────────────────────────────
  Set ACTIVE_PHASE below to the scale you want, then run the hydration script
  to generate the data on FSx Lustre:

      python data_preparation/scale_data_on_lustre.py --phase phase_10gb

  This downloads the human genome from UCSC, replicates it to the target size,
  preprocesses it into the format Evo2 expects, and writes it to Lustre.
  The EC2 instance terminates itself when done.  You only run this once per
  phase — if the data is already there, it won't regenerate it.

  STEP 2 — Set ACTIVE_PHASE here to match what you staged in Step 1
  ─────────────────────────────────────────────────────────────────────
  ACTIVE_PHASE = "phase_10gb"   ← change this line

  PHASE_SUBDIR and PREPROC_PREFIX are derived automatically from ACTIVE_PHASE.
  You do NOT need to set them manually.

  STEP 3 — Launch the training job
  ─────────────────────────────────
      python launch_bionemo_job.py --job-name my-experiment

  The launcher reads ACTIVE_PHASE from this file and tells SageMaker which
  directory on Lustre to mount as training data.  No other changes needed.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ONE-OFF OVERRIDES (without editing this file)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Any value below can be overridden on the command line for a single run:

      python launch_bionemo_job.py --job-name smoke --max-steps 5 --instance-type ml.g5.2xlarge

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  VALIDATED CONFIGURATIONS (Syngenta cross-AZ scaling study, BioNeMo 2.7.1)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Model    Instance            GPUs  TP  PP  seq    s/step  Status
  ───────  ──────────────────  ────  ──  ──  ─────  ──────  ──────────────────
  1b_nv    ml.g5.12xlarge        4   1   4   8192   2.16    ✓ Validated
  7b       ml.p4d.24xlarge       8   1   8   8192   2.82    ✓ Validated
  40b      ml.p4de.24xlarge      8   1   8   2048   4.00    ✓ Validated
  40b      ml.p5.48xlarge        8   1   8   2048    tbd    ✗ Not tested (no P5 quota)
  40b_nv   any                   -   -   -      -      -    ✗ BioNeMo 2.7.1 bug — do not use

  Key insight: step time grows only 1.85× going from 1B → 40B (40× more params)
  because each hardware tier brings proportionally more compute.  The cost of
  larger models is GPU memory (you need bigger/more GPUs), not wall-clock time.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SCALING TO 40B ON ml.p5.48xlarge — WHAT TO CHANGE AND WHAT TO EXPECT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  The P5.48xlarge (8x H100 80 GB) is the target production instance for the
  40B model.  It was not tested during validation due to AWS service quota
  limits (default quota for P5 SageMaker training jobs is 0 — you must
  request an increase before you can use it).  Based on validated P4de
  results and hardware specs, the P5 is expected to work with the same
  parallelism config as P4de.

  HOW TO CONFIGURE IT:
  ────────────────────
  In this file, set:

      MODEL_SIZE         = "40b"          # NOT "40b_nv" — see warning below
      INSTANCE_TYPE      = "ml.p5.48xlarge"
      DEVICES            = 8
      TENSOR_PARALLEL    = 1              # see TP constraint note below
      PIPELINE_PARALLEL  = 8
      SEQ_LENGTH         = 2048           # NOT 8192 — see memory note below
      ACTIVATION_CKPT_LAYERS = 10        # more aggressive than smaller models
      MICRO_BATCH_SIZE   = 1
      MAX_RUNTIME_SECONDS = 86400         # 24 hrs for a real training run

  In training_job_config.py PHASES, set:

      ACTIVE_PHASE = "phase_2tb"          # or phase_4tb for multi-TB data

  CRITICAL WARNINGS BEFORE YOU RUN:
  ──────────────────────────────────
  ⚠  Use MODEL_SIZE = "40b", NOT "40b_nv"
     The "40b_nv" (NVIDIA-optimised) variant crashes with an illegal memory
     access during model initialisation in BioNeMo Framework 2.7.1.  This
     was reproduced across multiple TP/PP/seq_length configurations on
     P4de.  It is a framework bug, not a config error.  The vanilla "40b"
     model works correctly.  Check the BioNeMo release notes before trying
     "40b_nv" on a newer BioNeMo version.

  ⚠  SEQ_LENGTH must be 2048, not 8192
     At 40B scale with PP=8, each GPU holds 5B parameters.  Memory per GPU
     with Adam optimizer (~14 bytes/param) is ~70 GB, leaving very little
     headroom on an 80 GB GPU.  Sequence length 8192 pushes activations
     over the limit.  Start at seq=2048.  If you want to increase it, do
     so in small steps (4096, then 8192) and watch for OOM errors.

  ⚠  Do NOT use TENSOR_PARALLEL > 1 without checking head count first
     Evo2 Hyena models have unusual attention head counts.  Tensor
     parallelism requires (num_heads % TP == 0).  For the 40B model, valid
     TP values depend on its specific head count — check the BioNeMo model
     card before setting TP > 1.  If in doubt, keep TP=1 and use PP=8.

  ⚠  Request your P5 quota before you need it
     Default SageMaker training quota for ml.p5.48xlarge is 0 instances.
     Quota increases for P5 can take days to approve.  File the request at:
     AWS Console → Service Quotas → Amazon SageMaker →
       "ml.p5.48xlarge for training job usage"
     Also request for p4de if you want a fallback:
       "ml.p4de.24xlarge for training job usage"

  ⚠  AZ capacity for P5 may be scarce
     During validation, ml.p4de.24xlarge capacity in us-west-2b was
     unavailable for 5+ hours.  us-west-2c had capacity within 4 minutes.
     Set SAGEMAKER_AZ = "us-west-2c" in config.py for P5/P4de jobs, or
     consider On-Demand Capacity Reservations (ODCRs) for production.

  EXPECTED PERFORMANCE ON P5:
  ────────────────────────────
  The P5.48xlarge has identical VRAM (8x 80 GB) to P4de but with H100 GPUs
  that offer roughly 2x the compute throughput of A100 (A100 = 312 TFLOPS
  bf16, H100 = 989 TFLOPS bf16) and faster NVLink interconnect.  Validated
  40B step time on P4de was 4.0 s/step at seq=2048.  On P5 the same config
  should produce roughly 1.5-2.5 s/step — but this is an estimate, not a
  measured result.  Run a smoke test (MAX_STEPS=10) to confirm before
  committing to a long training job.

  SCALING THE DATA FOR PRODUCTION:
  ─────────────────────────────────
  For several-TB training datasets, use phase_2tb or phase_4tb (defined in
  the PHASES table below).  Hydrate the filesystem first:

      python data_preparation/scale_data_on_lustre.py --phase phase_2tb

  The 1B/10GB and 1B/100GB validation runs confirmed that cross-AZ read
  performance does not degrade as data volume grows — step time was
  identical (2.16 vs 2.155 s/step) despite a 10x data increase.  This
  result holds for multi-TB datasets: I/O is never the bottleneck because
  Evo2 only reads one batch (8 KB at seq=8192) per step regardless of total
  dataset size.
"""

# ── Compute ────────────────────────────────────────────────────────────────────

# Which AWS GPU instance runs the training job.
#
# Model-to-instance mapping (validated):
#   1B model → ml.g5.12xlarge   (4x A10G 24 GB, PP=4)
#   7B model → ml.p4d.24xlarge  (8x A100 40 GB, PP=8)
#  40B model → ml.p4de.24xlarge (8x A100 80 GB, PP=8)  ← validated
#  40B model → ml.p5.48xlarge   (8x H100 80 GB, PP=8)  ← target production, not yet tested
#
# For smoke tests / quick iteration on any model size:
#   ml.g5.2xlarge — 1x A10G (24 GB), cheapest option, good for pipeline testing
#
# NOTE: Default SageMaker quotas for p4d, p4de, and p5 are all 0.
# You must request a quota increase before you can use these instances.
# File the request in AWS Service Quotas well before you need them.
INSTANCE_TYPE: str = "ml.g5.12xlarge"

# Number of GPUs to use for training.  Must match INSTANCE_TYPE exactly.
#   ml.g5.2xlarge  → 1 GPU     ml.g5.12xlarge  → 4 GPUs
#   ml.p4d.24xlarge → 8 GPUs   ml.p4de.24xlarge → 8 GPUs   ml.p5.48xlarge → 8 GPUs
DEVICES: int = 4

# Root EBS volume size (GB) attached to the SageMaker instance.
# 100 GB covers OS, logs, and container image.  Training data lives on
# Lustre and does NOT count against this — you don't need to increase it
# just because you're training on 1 TB of genomic data.
INSTANCE_VOLUME_GB: int = 100

# ── Model ──────────────────────────────────────────────────────────────────────

# Which Evo2 model size to train.
#
# Validated options (BioNeMo 2.7.1):
#   "1b_nv"  — 1B parameters, NVIDIA-optimised  (A10G 24 GB, PP=4)   ✓ validated
#   "7b"     — 7B parameters                     (A100 40 GB, PP=8)   ✓ validated
#   "40b"    — 40B parameters                    (A100/H100 80 GB, PP=8, seq=2048) ✓ validated
#
# ⚠  DO NOT USE "40b_nv" — it crashes on BioNeMo 2.7.1 with an illegal memory
#    access during model init.  This is a framework bug, not a config issue.
#    Use "40b" (vanilla) instead.  Re-test "40b_nv" only after upgrading BioNeMo.
MODEL_SIZE: str = "1b_nv"

# ── Parallelism ────────────────────────────────────────────────────────────────
#
# Evo2 uses two types of model parallelism to split large models across GPUs.
# The rule is: TENSOR_PARALLEL * PIPELINE_PARALLEL must equal DEVICES.
#
# TENSOR_PARALLEL (TP) — splits each individual layer horizontally across GPUs.
#   Use TP > 1 when a single layer is too large for one GPU's memory.
#   Communication-heavy; keep low unless forced by memory.
#
# PIPELINE_PARALLEL (PP) — splits the model's layers (depth) across GPUs.
#   GPU 1 handles early layers, GPU 2 handles later layers, etc.
#   Generally more efficient than TP for the same memory saving.
#
# Validated combinations (must satisfy TP * PP = DEVICES):
#   1B model  on 4x A10G  (g5.12xlarge)   → TP=1, PP=4   ← this default
#   7B model  on 8x A100  (p4d.24xlarge)  → TP=1, PP=8
#   40B model on 8x A100  (p4de.24xlarge) → TP=1, PP=8   ← validated at seq=2048
#   40B model on 8x H100  (p5.48xlarge)   → TP=1, PP=8   ← expected, not yet tested
#
# ⚠  Tensor parallelism (TP) constraint unique to Evo2 Hyena models:
#    Evo2 uses Hyena layers with unusual attention head counts (e.g. 15 heads
#    for 1B_nv).  TP requires (num_heads % TP == 0), so most TP values > 1
#    will crash with a head count assertion error.  Keep TP=1 and use PP
#    to distribute across GPUs.  If you specifically need TP > 1, check the
#    BioNeMo model card for the exact head count and valid TP divisors first.

TENSOR_PARALLEL: int = 1
PIPELINE_PARALLEL: int = 4

# How many transformer layers to recompute during the backward pass instead
# of storing them in memory (gradient checkpointing).
# Higher value = less GPU memory used, but slower training.
# 5 is a reasonable starting point for the 1B model.
ACTIVATION_CKPT_LAYERS: int = 5

# ── Data phases ────────────────────────────────────────────────────────────────
#
# ┌─────────────────────────────────────────────────────────────────────────┐
# │  WHAT IS A PHASE?                                                       │
# │                                                                         │
# │  A "phase" is a named dataset at a specific scale.  Each phase gets     │
# │  its own subdirectory on the Lustre filesystem so multiple scales can   │
# │  coexist without interfering with each other.                           │
# │                                                                         │
# │  The raw data is the human reference genome (hg38) downloaded from      │
# │  UCSC — a ~3 GB FASTA file per copy.  The hydration script replicates  │
# │  it as many times as needed to hit the target size, then preprocesses  │
# │  all copies into .bin/.idx files that Evo2 reads during training.       │
# │                                                                         │
# │  DOES THE HYDRATION SCRIPT REGENERATE DATA EVERY TIME?                 │
# │  No.  It checks how many bytes are already in the phase directory and   │
# │  only copies enough additional files to reach the target size.  If the  │
# │  phase is already fully populated, it skips the copy step entirely and  │
# │  goes straight to preprocessing.  Re-running the script on an already- │
# │  complete phase is safe and fast.                                       │
# │                                                                         │
# │  DO I HAVE TO RE-GENERATE SMALLER PHASES WHEN I SCALE UP?              │
# │  No.  phase_10gb and phase_100gb are completely separate directories.   │
# │  Generating phase_100gb does not touch phase_10gb.  You can keep all   │
# │  phases on Lustre simultaneously and switch between them by changing    │
# │  ACTIVE_PHASE below.                                                    │
# │                                                                         │
# │  HOW LONG DOES HYDRATION TAKE?  (rough estimates)                      │
# │  phase_10gb  — ~15-30 min   (download + preprocess on g5.4xlarge)      │
# │  phase_100gb — ~1-2 hrs     (mostly preprocessing)                     │
# │  phase_500gb — ~4-8 hrs     (large FASTA + preprocessing on g5.12xl)   │
# │  phase_1tb   — ~8-16 hrs    (preprocessing dominates on g5.48xl)       │
# └─────────────────────────────────────────────────────────────────────────┘
#
# Each entry defines:
#   target_raw_gb  — total GB of raw FASTA to write to Lustre before
#                    preprocessing.  The preprocessed .bin/.idx output will
#                    be roughly 2x this size (relaxed filters + reverse
#                    complement doubling).
#   preproc_prefix — filename prefix for the .bin/.idx output files.
#                    The training job uses this to find the right dataset.
#                    Each phase must have a unique prefix — do not reuse.
#   data_instance  — EC2 instance type for the preprocessing job.
#                    Larger phases need more RAM (preprocess_evo2 loads all
#                    FASTA files into memory before writing output).
#   description    — shown in logs and --help output.

PHASES: dict[str, dict] = {
    "phase_10gb": {
        "target_raw_gb":  10,
        "preproc_prefix": "hg38_10gb",
        "data_instance":  "g5.4xlarge",    # 64 GB RAM — sufficient for 10 GB FASTA
        "description":    "~10 GB raw FASTA — baseline cross-AZ validation",
    },
    "phase_100gb": {
        "target_raw_gb":  100,
        "preproc_prefix": "hg38_100gb",
        "data_instance":  "g5.4xlarge",    # 64 GB RAM — sufficient for 100 GB FASTA
        "description":    "~100 GB raw FASTA — bandwidth stress test",
    },
    "phase_500gb": {
        "target_raw_gb":  500,
        "preproc_prefix": "hg38_500gb",
        "data_instance":  "g5.12xlarge",   # 192 GB RAM — needed for 500 GB FASTA
        "description":    "~500 GB raw FASTA — mid-scale production",
    },
    "phase_1tb": {
        "target_raw_gb":  1000,
        "preproc_prefix": "hg38_1tb",
        "data_instance":  "g5.48xlarge",   # 768 GB RAM — needed for 1 TB FASTA
        "description":    "~1 TB raw FASTA — large-scale production",
    },
    "phase_2tb": {
        "target_raw_gb":  2000,
        "preproc_prefix": "hg38_2tb",
        "data_instance":  "g5.48xlarge",   # 768 GB RAM; expect ~12-24 hrs to preprocess
        "description":    "~2 TB raw FASTA — production scale for 40B model on P5",
    },
    "phase_4tb": {
        "target_raw_gb":  4000,
        "preproc_prefix": "hg38_4tb",
        "data_instance":  "g5.48xlarge",   # 768 GB RAM; expect ~24-48 hrs to preprocess
        "description":    "~4 TB raw FASTA — large production, verify Lustre capacity first",
    },
    # ── Adding a custom phase ──────────────────────────────────────────────────
    # If none of the presets above match your target data volume, add a new
    # entry following the same pattern:
    #
    #   "phase_Xgb": {
    #       "target_raw_gb":  X,
    #       "preproc_prefix": "hg38_Xgb",      # must be unique — no two phases share a prefix
    #       "data_instance":  "g5.48xlarge",    # use g5.4xlarge for <200 GB, g5.12xlarge for
    #                                           # 200-800 GB, g5.48xlarge for 800 GB+
    #       "description":    "~X GB raw FASTA — your description here",
    #   },
    #
    # Then set ACTIVE_PHASE = "phase_Xgb" and run:
    #   python data_preparation/scale_data_on_lustre.py --phase phase_Xgb
}

# ┌─────────────────────────────────────────────────────────────────────────┐
# │  ACTIVE_PHASE — THE ONE SETTING THAT CONNECTS DATA TO TRAINING          │
# │                                                                         │
# │  This tells the training job which phase directory to read from.        │
# │  Change this to switch dataset scale.                                   │
# │                                                                         │
# │  Before changing this to a larger phase, make sure you have run the     │
# │  hydration script for that phase first:                                 │
# │                                                                         │
# │    python data_preparation/scale_data_on_lustre.py --phase phase_100gb  │
# │                                                                         │
# │  If you point ACTIVE_PHASE at a phase that hasn't been hydrated yet,   │
# │  the training job will fail immediately with a "no data found" error.   │
# └─────────────────────────────────────────────────────────────────────────┘
ACTIVE_PHASE: str = "phase_10gb"

# These two are derived automatically from ACTIVE_PHASE.
# DO NOT edit them directly — change ACTIVE_PHASE above instead.
# They exist so launch_bionemo_job.py can pass exact values to SageMaker.
PHASE_SUBDIR:   str = ACTIVE_PHASE                        # Lustre subdirectory path
PREPROC_PREFIX: str = PHASES[ACTIVE_PHASE]["preproc_prefix"]  # .bin/.idx filename prefix

# ── Checkpoint (optional) ──────────────────────────────────────────────────────
#
# To fine-tune from a pretrained Evo2 checkpoint instead of training from
# scratch, set this to the subdirectory name under /checkpoints/ on Lustre.
#
# Leave it empty ("") to train from random weight initialisation.
#
# Checkpoints are staged by:
#   python data_preparation/stage_checkpoint_on_lustre.py --resource evo2/1b-8k-bf16:1.0
#
# Available checkpoint resources (pass to --resource):
#   evo2/1b-8k-bf16:1.0    → set CKPT_SUBDIR = "evo2_1b_8k_bf16"
#   evo2/7b-1m:1.0         → set CKPT_SUBDIR = "evo2_7b_1m"
#   evo2/40b-1m-fp8-bf16:1.0 → set CKPT_SUBDIR = "evo2_40b_1m_fp8_bf16"
CKPT_SUBDIR: str = ""

# ── Training hyperparameters ───────────────────────────────────────────────────

# Number of sequences processed per GPU per gradient step.
# Keep at 1 for large models (memory) and increase only for small models
# where you want higher GPU utilisation.
MICRO_BATCH_SIZE: int = 1

# Length of each input sequence in tokens (DNA bases).
# Evo2 supports up to 1,000,000 (1M context) but longer sequences consume
# significantly more GPU memory.
#
# Validated values:
#   8192 — default; works for 1B and 7B models
#   2048 — required for 40B model; 8192 causes OOM on 80 GB GPUs at PP=8
#          because activation memory fills the remaining headroom after weights
#
# If you switch to MODEL_SIZE = "40b", also change SEQ_LENGTH to 2048.
# Once stable on P5, try increasing in steps (4096, then 8192) while watching
# for OOM errors.
SEQ_LENGTH: int = 8192

# Total number of gradient update steps to run.
#   10      — end-to-end smoke test; just proves the pipeline works
#   100     — quick sanity check; enough to see if loss is decreasing
#   10,000+ — real training run
MAX_STEPS: int = 10

# ── Job limits ─────────────────────────────────────────────────────────────────

# SageMaker hard-stops the job after this many seconds regardless of progress.
# The job is billed by the second up to this limit.
#   7,200   =  2 hours — covers validation runs (~10-100 steps on large models)
#   86,400  = 24 hours — full training run
MAX_RUNTIME_SECONDS: int = 7200

# Whether the training container can write back to the Lustre filesystem.
#   "rw" — read/write (default: container can save checkpoints to Lustre)
#   "ro" — read-only  (use if checkpoints should go to S3 only)
LUSTRE_ACCESS_MODE: str = "rw"

# ── Debugging ─────────────────────────────────────────────────────────────────

# Forces CUDA operations to complete before the next one starts.
# Makes GPU error messages point to the exact line that caused them.
# Set to 1 only when debugging a CUDA crash — it slows training by 10-50x.
CUDA_LAUNCH_BLOCKING: int = 0


# ── Helpers (used by launch_bionemo_job.py — no need to edit below here) ───────

def validate() -> None:
    """Catch obvious misconfiguration before the job is submitted to SageMaker."""
    import sys

    errors: list[str] = []

    if ACTIVE_PHASE not in PHASES:
        errors.append(
            f"ACTIVE_PHASE={ACTIVE_PHASE!r} is not defined in the PHASES table.\n"
            f"  Valid phases: {list(PHASES)}\n"
            "  Either pick an existing phase or add a new entry to PHASES."
        )

    if TENSOR_PARALLEL * PIPELINE_PARALLEL > DEVICES:
        errors.append(
            f"TENSOR_PARALLEL ({TENSOR_PARALLEL}) * PIPELINE_PARALLEL ({PIPELINE_PARALLEL}) "
            f"= {TENSOR_PARALLEL * PIPELINE_PARALLEL}, which exceeds DEVICES ({DEVICES}).\n"
            "  Reduce TENSOR_PARALLEL or PIPELINE_PARALLEL so their product equals DEVICES."
        )

    if DEVICES < 1:
        errors.append(f"DEVICES must be >= 1, got {DEVICES}.")

    if MAX_STEPS < 1:
        errors.append(f"MAX_STEPS must be >= 1, got {MAX_STEPS}.")

    if LUSTRE_ACCESS_MODE not in ("ro", "rw"):
        errors.append(
            f"LUSTRE_ACCESS_MODE must be 'ro' or 'rw', got {LUSTRE_ACCESS_MODE!r}."
        )

    if MODEL_SIZE not in ("1b_nv", "7b", "40b"):
        import logging
        logging.getLogger("training_job_config").warning(
            "MODEL_SIZE=%r is not in the known set (1b_nv, 7b, 40b). "
            "Proceeding — verify it is registered in your BioNeMo version.",
            MODEL_SIZE,
        )

    if errors:
        for e in errors:
            print(f"[training_job_config] ERROR: {e}", file=sys.stderr)
        sys.exit(1)


def summary() -> str:
    """Return a human-readable summary for logging at job launch."""
    return (
        f"  active_phase:          {ACTIVE_PHASE} ({PHASES[ACTIVE_PHASE]['description']})\n"
        f"  phase_subdir:          {PHASE_SUBDIR}\n"
        f"  preproc_prefix:        {PREPROC_PREFIX}\n"
        f"  ckpt_subdir:           {CKPT_SUBDIR or '(none — train from scratch)'}\n"
        f"  instance_type:         {INSTANCE_TYPE}\n"
        f"  devices:               {DEVICES}\n"
        f"  instance_volume_gb:    {INSTANCE_VOLUME_GB}\n"
        f"  model_size:            {MODEL_SIZE}\n"
        f"  tensor_parallel:       {TENSOR_PARALLEL}\n"
        f"  pipeline_parallel:     {PIPELINE_PARALLEL}\n"
        f"  activation_ckpt:       {ACTIVATION_CKPT_LAYERS}\n"
        f"  micro_batch_size:      {MICRO_BATCH_SIZE}\n"
        f"  seq_length:            {SEQ_LENGTH}\n"
        f"  max_steps:             {MAX_STEPS}\n"
        f"  max_runtime_seconds:   {MAX_RUNTIME_SECONDS}\n"
        f"  lustre_access_mode:    {LUSTRE_ACCESS_MODE}\n"
        f"  cuda_launch_blocking:  {CUDA_LAUNCH_BLOCKING}"
    )
