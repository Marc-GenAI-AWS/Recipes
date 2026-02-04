# BioNeMo Evo2 Training Project

Training Evo2 models using BioNeMo on SageMaker.

## Project Structure

```
bionemo-project/
├── src/
│   └── train.py                # Main Evo2 training script
├── launch_training.py          # Kicks off SageMaker training job
├── bionemo_interactive.ipynb   # Interactive notebook with the BioNemo container
├── test_local.sh               # Test custom script locally
├── test_cli.sh                 # Test using built-in train_evo2 CLI
└── README.md
```

## Prerequisites

### 1. Start the BioNeMo Container

```bash
# Login to ECR
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin <YOUR_AWS_ACCOUNT_ID?.<REGION>.amazonaws.com/<IMAGE>:<TAG>

# Pull image from ECR
docker pull <YOUR_AWS_ACCOUNT_ID?.dkr.ecr.<REGION>.amazonaws.com/<IMAGE>:<TAG>

# Run container with required settings
docker run -d \
    --name bionemo \
    --gpus all \
    --ipc=host \
    --ulimit memlock=-1 \
    --ulimit stack=67108864 \
    -e TRITON_LIBCUDA_PATH=/usr/lib/x86_64-linux-gnu/libcuda.so.1 \
    -p 8888:8888 \
    -p 5000:5000 \
    -v /home/ec2-user/SageMaker:/workspace \
    <YOUR_AWS_ACCOUNT_ID?.dkr.ecr.<REGION>.amazonaws.com/<IMAGE>:<TAG> \
    tail -f /dev/null
```

### 2. Verify Setup

```bash
docker ps
docker exec bionemo nvidia-smi
```

## Quick Start

### Option 1: Test Using Built-in CLI

```bash
chmod +x test_cli.sh
./test_cli.sh
```

Or manually:

```bash
docker exec bionemo train_evo2 \
    --mock-data \
    --model-size 1b \
    --num-nodes 1 \
    --devices 4 \
    --seq-length 128 \
    --micro-batch-size 1 \
    --global-batch-size 4 \
    --max-steps 10 \
    --result-dir /workspace/evo2_test \
    --experiment-name test_run \
    --disable-checkpointing \
    --limit-val-batches 1
```

### Option 2: Test Custom Training Script

```bash
chmod +x test_local.sh
./test_local.sh
```

Or manually:

```bash
docker exec bionemo python /workspace/bionemo-project/src/train.py \
    --mock-data \
    --model-size 1b \
    --max-steps 10 \
    --devices 4
```

### Option 3: Launch SageMaker Training Job

```bash
python launch_training.py
```

## Model Sizes

| Model | Parameters | Min GPU Memory | Recommended Instance |
|-------|------------|----------------|----------------------|
| test  | Small      | ~8GB           | ml.g4dn.xlarge       |
| 1b    | 1.1B       | ~80GB (4 GPUs) | ml.g5.12xlarge       |
| 7b    | 7B         | ~160GB+        | ml.p4d.24xlarge      |

## Instance Types

| Instance | GPUs | GPU Memory | Good For |
|----------|------|------------|----------|
| ml.g4dn.xlarge | 1x T4 | 16GB | test model only |
| ml.g5.2xlarge | 1x A10G | 24GB | test model only |
| ml.g5.12xlarge | 4x A10G | 96GB | 1b model |
| ml.g5.24xlarge | 4x A10G | 96GB | 1b model (more CPU/RAM) |
| ml.p4d.24xlarge | 8x A100 | 320GB | 7b model |

## Key Hyperparameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--model-size` | Model variant (test, 1b, 7b) | 1b |
| `--max-steps` | Training steps | 10 |
| `--seq-length` | Sequence length | 128 |
| `--micro-batch-size` | Batch size per GPU | 1 |
| `--global-batch-size` | Total batch size | micro * devices |
| `--lr` | Learning rate | 3e-4 |
| `--devices` | Number of GPUs | auto-detect |

## Data Options

### Mock Data (Testing)
```bash
--mock-data
```

### Real Data (Production)
```bash
--data-config /path/to/dataset.yaml
--dataset-dir /path/to/data
```

See BioNeMo documentation for dataset format requirements.

## Troubleshooting

### Triton Unicode Error
Set environment variable:
```bash
-e TRITON_LIBCUDA_PATH=/usr/lib/x86_64-linux-gnu/libcuda.so.1
```

### Out of Memory
- Use a larger instance
- Reduce `--seq-length`
- Reduce `--micro-batch-size`
- Use `--model-size test` for testing

### Container Exits Immediately
Add `tail -f /dev/null` to keep it running:
```bash
docker run -d ... IMAGE tail -f /dev/null
```

## Extending for Custom Data

To use your own training data:

1. Prepare FASTA files or dataset config YAML
2. Upload to S3
3. Modify `launch_training.py`:
   ```python
   TRAIN_DATA_S3 = "s3://your-bucket/training-data/"
   HYPERPARAMETERS = {
       "data-config": "/opt/ml/input/data/train/config.yaml",
       # Remove "mock-data"
   }
   ```

4. Extend `src/train.py` to handle real data loading

## References

- [BioNeMo Documentation](https://docs.nvidia.com/bionemo/)
- [Evo2 Paper](https://arxiv.org/abs/2403.19548)
- [NeMo Framework](https://github.com/NVIDIA/NeMo)
