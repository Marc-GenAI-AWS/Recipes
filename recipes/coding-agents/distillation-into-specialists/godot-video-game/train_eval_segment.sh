#!/bin/bash
# Train the segment's adapter on SageMaker and evaluate it on
# the held-out briefs when the artifact lands (MODELS=... for a bake-off).
#   pipeline/train_eval_segment.sh <segment> <data run name>   e.g. vegetation veg1
set -uo pipefail
cd "$(dirname "$0")"
SEG=$1; RUN=$2
# synthetic repair examples (make_repair_pairs.py) don't count toward the minimum
N=$(grep -vc '"mode": "repair"' runs/$RUN/sft/train.jsonl 2>/dev/null || echo 0)
MIN=${MIN_EXAMPLES:-100}   # below this an adapter cannot approach the teacher (sky needed ~250); don't spend on it
if [ "$N" -lt "$MIN" ]; then echo "== $SEG: only $N training examples in runs/$RUN (minimum $MIN); not training"; exit 0; fi
: "${AWS_REGION:?set AWS_REGION}" "${SAGEMAKER_BUCKET:?set SAGEMAKER_BUCKET}"
B=s3://$SAGEMAKER_BUCKET/${S3_PREFIX:-specialist-pipeline}/$SEG/models
declare -A JOBS
# One specialist size for every segment (decision 2026-09-13): 3B. Override with MODELS="a b".
for m in ${MODELS:-${BASE_MODEL:-Qwen/Qwen2.5-Coder-3B-Instruct}}; do
  tag=$(echo $m | sed 's/.*Coder-//; s/-Instruct//' | tr 'A-Z.' 'a-zp')
  echo "== $(date +%T) launching $SEG $tag"
  job=""
  for try in $(seq 1 40); do   # the region allows one training instance per size: wait for a slot
    for inst in ml.g6e.xlarge ml.g6e.2xlarge; do
      out=$(${PYTHON:-python3} pipeline/sagemaker/launch_sft.py --data runs/$RUN/sft --segment $SEG --spot 0 --instance $inst --model $m 2>&1 | grep '^launched')
      job=$(echo "$out" | sed 's/launched \([^;]*\);.*/\1/')
      [ -n "$job" ] && break
    done
    [ -n "$job" ] && break
    echo "   no free training slot (try $try); waiting"; sleep 90
  done
  if [ -z "$job" ]; then echo "== could not launch $SEG $tag"; continue; fi
  echo "   $job"
  JOBS[$tag]=$job
  sleep 65
done
for tag in "${!JOBS[@]}"; do
  job=${JOBS[$tag]}
  echo "== $(date +%T) waiting for $job"
  # wait on the job status, not on model.tar.gz: SageMaker uploads a 236-byte model.tar.gz for failed jobs too
  while true; do
    st=$(aws sagemaker describe-training-job --training-job-name $job --region $AWS_REGION --query TrainingJobStatus --output text 2>/dev/null)
    [ "$st" = "Completed" ] && break
    if [ "$st" = "Failed" ] || [ "$st" = "Stopped" ]; then echo "== $job $st"; aws sagemaker describe-training-job --training-job-name $job --region $AWS_REGION --query FailureReason --output text | cut -c1-300; continue 2; fi
    sleep 60
  done
  echo "== $(date +%T) evaluating $job as eval-$RUN-$tag"
  ./eval_specialist.sh "$B/$job/output/model.tar.gz" "eval-$RUN-$tag" runs/$RUN/sft/heldout_briefs.jsonl $SEG > runs/eval-$RUN-$tag.log 2>&1 || echo "== eval-$RUN-$tag FAILED"
  grep -A 9 '"heldout_briefs"' runs/eval-$RUN-$tag.log | head -10
done
echo "== $(date +%T) $SEG train/eval done"
