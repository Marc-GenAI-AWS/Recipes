#!/bin/bash
# SageMaker entrypoint for cross-AZ FSx-for-Lustre + BioNeMo Evo2 training.
#
# SageMaker natively mounts the FSx for Lustre filesystem at
# /opt/ml/input/data/<channel_name>/ via FileSystemConfig. No manual mount,
# no nfs-common install, no CAP_SYS_ADMIN dance.
#
# Required env vars (set by launch_bionemo_job.py):
#   LUSTRE_CHANNEL     - channel name SageMaker mounted Lustre under
#                        (resolves to /opt/ml/input/data/$LUSTRE_CHANNEL)
#   PHASE_SUBDIR       - subdir under the channel for phase data, e.g. phase_10gb
#   CKPT_SUBDIR        - (optional) subdir under the channel for the checkpoint.
#                        If unset or dir missing, train from scratch.
#   PREPROC_PREFIX     - preprocess output prefix (e.g. hg38_uint8_distinct)
#   MODEL_SIZE         - e.g. 1b_nv, 40b_nv
#   MAX_STEPS          - e.g. 10
#   MICRO_BATCH_SIZE   - e.g. 1
#   SEQ_LENGTH         - e.g. 8192
#   DEVICES / TENSOR_PARALLEL / PIPELINE_PARALLEL
#   FSX_AZ / TRAINING_AZ - for CloudWatch metric dimensions (cross-AZ flag)
#   ACTIVATION_CKPT_LAYERS - int, for --activation-checkpoint-recompute-num-layers

set -euxo pipefail

echo "=== bionemo_entrypoint start $(date -u +%FT%TZ) ==="
: "${LUSTRE_CHANNEL:=training}"
: "${PHASE_SUBDIR:=phase_10gb}"
: "${CKPT_SUBDIR:=}"
: "${PREPROC_PREFIX:=hg38_uint8_distinct}"
: "${MODEL_SIZE:=1b_nv}"
: "${MAX_STEPS:=10}"
: "${MICRO_BATCH_SIZE:=1}"
: "${SEQ_LENGTH:=8192}"
: "${DEVICES:=1}"
: "${TENSOR_PARALLEL:=1}"
: "${PIPELINE_PARALLEL:=1}"
: "${ACTIVATION_CKPT_LAYERS:=5}"

# Help with fragmentation
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"

# Synchronous CUDA error reporting — makes crashes show the real faulting kernel
# instead of a random later API call. Slower but critical for debugging.
export CUDA_LAUNCH_BLOCKING="${CUDA_LAUNCH_BLOCKING:-0}"
echo "CUDA_LAUNCH_BLOCKING=$CUDA_LAUNCH_BLOCKING"

LUSTRE_ROOT="/opt/ml/input/data/${LUSTRE_CHANNEL}"
PHASE_DIR="${LUSTRE_ROOT}/${PHASE_SUBDIR}"
PREPROC_DIR="${PHASE_DIR}/preprocessed"

echo "  LUSTRE_ROOT=${LUSTRE_ROOT}"
echo "  PHASE_DIR=${PHASE_DIR}"
echo "  PREPROC_DIR=${PREPROC_DIR}"
echo "  MODEL_SIZE=${MODEL_SIZE}"
echo "  DEVICES=${DEVICES}  TP=${TENSOR_PARALLEL}  PP=${PIPELINE_PARALLEL}"

# Optional checkpoint dir
if [ -n "$CKPT_SUBDIR" ]; then
    CKPT_DIR="${LUSTRE_ROOT}/${CKPT_SUBDIR}"
    if [ -d "$CKPT_DIR" ]; then
        echo "  CKPT_DIR=${CKPT_DIR} (will fine-tune)"
        CKPT_ARG="--ckpt-dir $CKPT_DIR"
    else
        echo "  CKPT_SUBDIR was set to '$CKPT_SUBDIR' but dir missing; training from scratch"
        CKPT_ARG=""
    fi
else
    echo "  No CKPT_SUBDIR set; training from scratch"
    CKPT_ARG=""
fi

# ---- Sanity checks --------------------------------------------------------
ls "$LUSTRE_ROOT" || { echo "ERROR: $LUSTRE_ROOT not accessible"; exit 1; }

if ! ls ${PREPROC_DIR}/${PREPROC_PREFIX}_byte-level_*.bin 1>/dev/null 2>&1; then
    echo "ERROR: no preprocessed bin/idx under $PREPROC_DIR with prefix $PREPROC_PREFIX"
    ls "$PREPROC_DIR" || true
    exit 1
fi

# ---- Write training_data_config.yaml --------------------------------------
DATASET_CONFIG=/tmp/training_data_config.yaml
cat > "$DATASET_CONFIG" <<EOF
- dataset_prefix: ${PREPROC_DIR}/${PREPROC_PREFIX}_byte-level_train
  dataset_split: train
  dataset_weight: 1.0
- dataset_prefix: ${PREPROC_DIR}/${PREPROC_PREFIX}_byte-level_val
  dataset_split: validation
  dataset_weight: 1.0
- dataset_prefix: ${PREPROC_DIR}/${PREPROC_PREFIX}_byte-level_test
  dataset_split: test
  dataset_weight: 1.0
EOF
echo "=== training_data_config.yaml ==="
cat "$DATASET_CONFIG"

# ---- Determine cross-AZ for metrics ---------------------------------------
CROSS_AZ="false"
if [ -n "${FSX_AZ:-}" ] && [ -n "${TRAINING_AZ:-}" ] && [ "$FSX_AZ" != "$TRAINING_AZ" ]; then
    CROSS_AZ="true"
fi

# ---- Triton ldconfig UnicodeDecodeError workaround ------------------------
LIBCUDA_DIR=$(dirname "$(find /usr -name 'libcuda.so*' 2>/dev/null | head -1)")
if [ -z "$LIBCUDA_DIR" ]; then
    LIBCUDA_DIR=/usr/lib/x86_64-linux-gnu
fi
export TRITON_LIBCUDA_PATH="$LIBCUDA_DIR"
echo "TRITON_LIBCUDA_PATH=$TRITON_LIBCUDA_PATH"
ls -la "$LIBCUDA_DIR"/libcuda* 2>&1 || true

# ---- Start nvidia-smi background sampler ----------------------------------
# Emits one csv line per GPU every 5s, prefixed so we can grep/parse later.
SMI_LOG=/tmp/nvidia_smi_samples.csv
echo "timestamp,index,util_gpu_pct,mem_used_mib,mem_total_mib,temp_c" > "$SMI_LOG"
(
    while true; do
        nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total,temperature.gpu \
            --format=csv,noheader,nounits 2>/dev/null \
            | awk -v t=$(date +%s) '{print t","$0}' >> "$SMI_LOG"
        # Also echo to stdout with NVSMI prefix for CloudWatch Logs visibility
        nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total,temperature.gpu \
            --format=csv,noheader,nounits 2>/dev/null \
            | sed "s/^/[NVSMI $(date +%s)] /"
        sleep 5
    done
) &
SMI_PID=$!
echo "nvidia-smi sampler PID=$SMI_PID"

# ---- Run training ---------------------------------------------------------
RESULT_DIR=/opt/ml/model
mkdir -p "$RESULT_DIR"

TRAIN_START=$(date +%s)
# shellcheck disable=SC2086
train_evo2 \
    --dataset-config "$DATASET_CONFIG" \
    $CKPT_ARG \
    --model-size "$MODEL_SIZE" \
    --seq-length "$SEQ_LENGTH" \
    --micro-batch-size "$MICRO_BATCH_SIZE" \
    --max-steps "$MAX_STEPS" \
    --val-check-interval $(( MAX_STEPS / 2 > 1 ? MAX_STEPS / 2 : 1 )) \
    --limit-val-batches 2 \
    --log-every-n-steps 1 \
    --num-nodes 1 \
    --devices "$DEVICES" \
    --tensor-parallel-size "$TENSOR_PARALLEL" \
    --pipeline-model-parallel-size "$PIPELINE_PARALLEL" \
    --context-parallel-size 1 \
    --use-precision-aware-optimizer \
    --bf16-main-grads \
    --activation-checkpoint-recompute-num-layers "$ACTIVATION_CKPT_LAYERS" \
    --experiment-name "cross_az_${PHASE_SUBDIR}_${MODEL_SIZE}" \
    --result-dir "$RESULT_DIR" \
    --create-tensorboard-logger \
    --early-stop-on-step "$MAX_STEPS" \
    --ckpt-async-save \
    2>&1 | tee /tmp/train_evo2.log
TRAIN_RC=${PIPESTATUS[0]}

TRAIN_SECS=$(( $(date +%s) - TRAIN_START ))
TRAIN_END=$(date +%s)

# Stop the sampler
kill $SMI_PID 2>/dev/null || true
wait $SMI_PID 2>/dev/null || true

echo "=== train_evo2 exit=${TRAIN_RC} wall_clock=${TRAIN_SECS}s ==="

# ---- Parse nvidia-smi samples for summary ---------------------------------
# Columns: timestamp,index,util_gpu_pct,mem_used_mib,mem_total_mib,temp_c
SUMMARY=/tmp/gpu_summary.txt
{
    echo "=== GPU summary ==="
    awk -F',' 'NR>1 {
        idx=$2;
        util[idx] += $3; util_n[idx] += 1;
        if ($4 > peak_mem[idx]) peak_mem[idx] = $4;
        total[idx] = $5;
    } END {
        for (i in util) {
            printf "GPU%s: avg_util=%.1f%% peak_vram=%d/%d MiB\n", i, util[i]/util_n[i], peak_mem[i], total[i];
        }
    }' "$SMI_LOG" | sort
} | tee "$SUMMARY"

# Parse per-iter step time from train log for AvgStepTime + TokensPerSec
STEP_TIMES=$(grep -oE 'train_step_timing in s: [0-9.]+' /tmp/train_evo2.log | awk '{print $NF}')
echo "=== per-iter step times ==="
echo "$STEP_TIMES"
AVG_STEP=$(echo "$STEP_TIMES" | awk '{s+=$1; n+=1} END {if (n>0) printf "%.3f", s/n; else print "0"}')
echo "AVG_STEP=${AVG_STEP}s"

# Tokens/sec = seq_length * micro_batch_size * data_parallel / avg_step
DP=$(( DEVICES / (TENSOR_PARALLEL * PIPELINE_PARALLEL) ))
if [ "$DP" -lt 1 ]; then DP=1; fi
TOKENS_PER_SEC=$(awk -v s=$SEQ_LENGTH -v b=$MICRO_BATCH_SIZE -v dp=$DP -v t=$AVG_STEP 'BEGIN {if (t>0) printf "%.0f", s*b*dp/t; else print "0"}')
echo "TOKENS_PER_SEC=${TOKENS_PER_SEC}"

# ---- Publish summary metrics to CloudWatch --------------------------------
# Wrap in timeout because VPC has no CW interface endpoint.
publish_metric() {
    local name=$1 value=$2 unit=$3
    timeout 15 /usr/local/bin/aws cloudwatch put-metric-data --region us-west-2 \
        --namespace CrossAZValidation/ScaleTest \
        --metric-name "$name" --unit "$unit" --value "$value" \
        --dimensions ModelSize=${MODEL_SIZE},DataVolume=${PHASE_SUBDIR},CrossAZ=${CROSS_AZ} \
        2>&1 || echo "  cloudwatch put-metric-data $name failed/timed out"
}

publish_metric TrainingWallClock "$TRAIN_SECS" Seconds
publish_metric AvgStepTime "$AVG_STEP" Seconds
publish_metric TokensPerSec "$TOKENS_PER_SEC" "Count/Second"

# Per-GPU peak VRAM
awk -F',' 'NR>1 && $4 > peak[$2] {peak[$2]=$4} END {for (i in peak) print i, peak[i]}' "$SMI_LOG" \
    | while read idx peak_mib; do
        publish_metric "PeakVRAMGPU${idx}" "$peak_mib" Megabytes
    done

# Overall avg GPU util
AVG_UTIL=$(awk -F',' 'NR>1 {s+=$3; n+=1} END {if (n>0) printf "%.1f", s/n; else print "0"}' "$SMI_LOG")
publish_metric AvgGPUUtil "$AVG_UTIL" Percent

# ---- Save artifacts to /opt/ml/model so SageMaker uploads them ------------
cp "$SMI_LOG" "$RESULT_DIR/nvidia_smi_samples.csv" 2>/dev/null || true
cp "$SUMMARY" "$RESULT_DIR/gpu_summary.txt" 2>/dev/null || true
cp /tmp/train_evo2.log "$RESULT_DIR/train_evo2.log" 2>/dev/null || true
cat > "$RESULT_DIR/run_metadata.json" <<JSON_EOF
{
  "model_size": "${MODEL_SIZE}",
  "data_volume": "${PHASE_SUBDIR}",
  "devices": ${DEVICES},
  "tensor_parallel": ${TENSOR_PARALLEL},
  "pipeline_parallel": ${PIPELINE_PARALLEL},
  "data_parallel": ${DP},
  "seq_length": ${SEQ_LENGTH},
  "micro_batch_size": ${MICRO_BATCH_SIZE},
  "max_steps": ${MAX_STEPS},
  "train_wall_clock_seconds": ${TRAIN_SECS},
  "avg_step_time_seconds": ${AVG_STEP},
  "tokens_per_second": ${TOKENS_PER_SEC},
  "avg_gpu_util_percent": ${AVG_UTIL},
  "train_start_unix": ${TRAIN_START},
  "train_end_unix": ${TRAIN_END},
  "cross_az": "${CROSS_AZ}",
  "checkpoint_used": "${CKPT_ARG:-none}",
  "train_rc": ${TRAIN_RC}
}
JSON_EOF
cat "$RESULT_DIR/run_metadata.json"

du -sh "$RESULT_DIR" || true
ls -lh "$RESULT_DIR" || true

echo "=== bionemo_entrypoint done $(date -u +%FT%TZ) exit=${TRAIN_RC} ==="
exit $TRAIN_RC
