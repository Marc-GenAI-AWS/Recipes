"""
Evo2 Training Script - Entry point for SageMaker training job.
Uses BioNeMo's Evo2 training infrastructure.
"""
import argparse
import os
import sys
import logging

# Suppress harmless import warnings
logging.getLogger("nemo.utils.import_utils").setLevel(logging.ERROR)

import torch
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Evo2 Training Script")
    
    # Model configuration
    parser.add_argument('--model-size', type=str, default='1b',
                        choices=['test', '1b', '7b', '1b_nv', '7b_nv'],
                        help='Model size to train')
    
    # Training hyperparameters
    parser.add_argument('--max-steps', type=int, default=10)
    parser.add_argument('--seq-length', type=int, default=128)
    parser.add_argument('--micro-batch-size', type=int, default=1)
    parser.add_argument('--global-batch-size', type=int, default=None,
                        help='Global batch size. Defaults to micro_batch_size * devices')
    parser.add_argument('--lr', type=float, default=3e-4, help='Learning rate')
    parser.add_argument('--min-lr', type=float, default=3e-5, help='Min learning rate')
    parser.add_argument('--warmup-steps', type=int, default=100)
    parser.add_argument('--weight-decay', type=float, default=0.01)
    
    # Hardware configuration
    parser.add_argument('--num-nodes', type=int, default=1)
    parser.add_argument('--devices', type=int, default=None,
                        help='Number of GPUs. Defaults to all available.')
    
    # Data configuration
    parser.add_argument('--mock-data', action='store_true', default=True,
                        help='Use mock data for testing')
    parser.add_argument('--data-config', type=str, default=None,
                        help='Path to dataset config YAML')
    parser.add_argument('--train-data-dir', type=str,
                        default=os.environ.get('SM_CHANNEL_TRAIN', None),
                        help='Training data directory')
    
    # Output configuration
    parser.add_argument('--result-dir', type=str,
                        default=os.environ.get('SM_MODEL_DIR', '/workspace/evo2_results'))
    parser.add_argument('--experiment-name', type=str, default='evo2_training')
    
    # Checkpointing
    parser.add_argument('--disable-checkpointing', action='store_true', default=False)
    parser.add_argument('--ckpt-dir', type=str, default=None,
                        help='Checkpoint directory to resume from')
    
    # Validation
    parser.add_argument('--limit-val-batches', type=int, default=5)
    parser.add_argument('--val-check-interval', type=int, default=100)
    
    # Logging
    parser.add_argument('--log-every-n-steps', type=int, default=1)
    parser.add_argument('--create-tensorboard-logger', action='store_true', default=False)
    
    return parser.parse_args()


def get_num_gpus():
    """Detect number of available GPUs."""
    if torch.cuda.is_available():
        return torch.cuda.device_count()
    return 1


def train_with_mock_data(args):
    """Train using mock data - good for testing."""
    from nemo.collections.common.tokenizers.bytelevel_tokenizers import get_nmt_tokenizer
    from bionemo.llm.data.datamodule import MockDataModule
    from bionemo.evo2.models.mamba import MambaModel, MAMBA_MODEL_OPTIONS
    from bionemo.llm.utils.logger_utils import setup_nemo_lightning_logger
    from megatron.core.distributed import DistributedDataParallelConfig
    from megatron.core.optimizer import OptimizerConfig
    from nemo.lightning.pytorch.optim import CosineAnnealingScheduler, MegatronOptimizerModule
    import nemo.lightning as nl
    
    # Determine devices
    devices = args.devices or get_num_gpus()
    global_batch_size = args.global_batch_size or (args.micro_batch_size * devices)
    
    print("=" * 60)
    print("Evo2 Training Configuration")
    print("=" * 60)
    print(f"Model size: {args.model_size}")
    print(f"Devices: {devices}")
    print(f"Sequence length: {args.seq_length}")
    print(f"Micro batch size: {args.micro_batch_size}")
    print(f"Global batch size: {global_batch_size}")
    print(f"Max steps: {args.max_steps}")
    print(f"Learning rate: {args.lr}")
    print(f"Result dir: {args.result_dir}")
    print("=" * 60)
    
    # Setup tokenizer
    print("\nSetting up tokenizer...")
    tokenizer = get_nmt_tokenizer("byte-level")
    
    # Setup mock data module
    print("Setting up mock data module...")
    data_module = MockDataModule(
        seq_length=args.seq_length,
        micro_batch_size=args.micro_batch_size,
        global_batch_size=global_batch_size,
        num_train_samples=args.max_steps * global_batch_size,
        num_val_samples=args.limit_val_batches * global_batch_size,
        num_test_samples=1,
        num_workers=4,
        tokenizer=tokenizer,
    )
    
    # Setup model config
    print(f"\nSetting up {args.model_size} model...")
    if args.model_size not in MAMBA_MODEL_OPTIONS:
        raise ValueError(f"Unknown model size: {args.model_size}. "
                        f"Available: {list(MAMBA_MODEL_OPTIONS.keys())}")
    
    model_config = MAMBA_MODEL_OPTIONS[args.model_size](
        seq_length=args.seq_length,
        calculate_per_token_loss=True,
    )
    
    # Create model
    model = MambaModel(model_config, tokenizer=tokenizer)
    
    # Setup logger
    print("\nSetting up logger...")
    result_dir = Path(args.result_dir)
    result_dir.mkdir(parents=True, exist_ok=True)
    
    nemo_logger = setup_nemo_lightning_logger(
        root_dir=result_dir,
        name=args.experiment_name,
        initialize_tensorboard_logger=args.create_tensorboard_logger,
    )
    
    # Setup DDP config
    ddp_config = DistributedDataParallelConfig(
        check_for_nan_in_grad=True,
        grad_reduce_in_fp32=False,
    )
    
    # Setup strategy
    print("\nSetting up training strategy...")
    strategy = nl.MegatronStrategy(
        ddp=ddp_config,
        tensor_model_parallel_size=1,
        pipeline_model_parallel_size=1,
        context_parallel_size=1,
        pipeline_dtype=torch.bfloat16,
        ckpt_load_optimizer=True,
        ckpt_save_optimizer=True,
    )
    
    # Setup trainer
    print("\nSetting up trainer...")
    trainer = nl.Trainer(
        devices=devices,
        num_nodes=args.num_nodes,
        max_steps=args.max_steps,
        accelerator="gpu",
        strategy=strategy,
        log_every_n_steps=args.log_every_n_steps,
        limit_val_batches=args.limit_val_batches,
        num_sanity_val_steps=0,
        use_distributed_sampler=False,
        plugins=nl.MegatronMixedPrecision(
            precision="bf16-mixed",
            params_dtype=torch.bfloat16,
        ),
        val_check_interval=args.val_check_interval,
        enable_checkpointing=not args.disable_checkpointing,
    )
    
    # Setup logger
    nemo_logger.setup(trainer, resume_if_exists=True)
    
    # Setup optimizer
    print("\nSetting up optimizer...")
    opt_config = OptimizerConfig(
        optimizer="adam",
        lr=args.lr,
        adam_beta1=0.9,
        adam_beta2=0.95,
        weight_decay=args.weight_decay,
        clip_grad=1.0,
        adam_eps=1e-8,
        use_distributed_optimizer=True,
        bf16=True,
    )
    
    sched = CosineAnnealingScheduler(
        max_steps=args.max_steps,
        warmup_steps=args.warmup_steps,
        min_lr=args.min_lr,
    )
    
    opt = MegatronOptimizerModule(opt_config, sched)
    opt.connect(model)
    
    # Train
    print("\n" + "=" * 60)
    print("Starting training...")
    print("=" * 60)
    
    trainer.fit(model, data_module)
    
    print("\n" + "=" * 60)
    print("Training complete!")
    print("=" * 60)
    print(f"Results saved to: {args.result_dir}")
    
    return trainer


def main():
    args = parse_args()
    
    print("=" * 60)
    print("Evo2 Training Script")
    print("=" * 60)
    
    # Use mock data training for now
    if args.mock_data or args.data_config is None:
        print("Using mock data for training...")
        trainer = train_with_mock_data(args)
    else:
        # For real data, you would implement data loading here
        # or call train_evo2 CLI with appropriate arguments
        raise NotImplementedError(
            "Real data training not yet implemented. "
            "Use --mock-data for testing or extend this script."
        )
    
    return trainer


if __name__ == '__main__':
    main()
