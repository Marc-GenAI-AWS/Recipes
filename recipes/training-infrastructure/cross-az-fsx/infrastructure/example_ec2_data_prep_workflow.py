#!/usr/bin/env python3
"""
Example EC2 Data Preparation Workflow

Demonstrates how to use the EC2 data preparation infrastructure
to prepare genomic datasets at different scales.
"""

import json
import logging
from pathlib import Path

from prepare_dataset_on_ec2 import DatasetPreparationOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def prepare_10gb_dataset(fsx_file_system_id: str):
    """
    Prepare 10GB dataset (chr1, chr2)
    
    Args:
        fsx_file_system_id: FSx file system ID
    """
    logger.info("=" * 80)
    logger.info("Preparing 10GB Dataset")
    logger.info("=" * 80)
    
    orchestrator = DatasetPreparationOrchestrator(
        region="us-west-2",
        availability_zone="us-west-2a"
    )
    
    result = orchestrator.prepare_dataset(
        fsx_file_system_id=fsx_file_system_id,
        fsx_mount_name="/genomics",
        chromosomes=["chr1", "chr2"],
        dest_subdir="phase_10gb",
        volume_size="10GB",
        auto_terminate=True,
        monitor_interval=60,
        max_runtime_hours=2
    )
    
    logger.info("10GB dataset preparation complete")
    logger.info(f"Duration: {result['duration_human']}")
    logger.info(f"Instance: {result['instance_id']}")
    
    return result


def prepare_100gb_dataset(fsx_file_system_id: str):
    """
    Prepare 100GB dataset (chr1-chr10)
    
    Args:
        fsx_file_system_id: FSx file system ID
    """
    logger.info("=" * 80)
    logger.info("Preparing 100GB Dataset")
    logger.info("=" * 80)
    
    orchestrator = DatasetPreparationOrchestrator(
        region="us-west-2",
        availability_zone="us-west-2a"
    )
    
    chromosomes = [f"chr{i}" for i in range(1, 11)]
    
    result = orchestrator.prepare_dataset(
        fsx_file_system_id=fsx_file_system_id,
        fsx_mount_name="/genomics",
        chromosomes=chromosomes,
        dest_subdir="phase_100gb",
        volume_size="100GB",
        auto_terminate=True,
        monitor_interval=60,
        max_runtime_hours=3
    )
    
    logger.info("100GB dataset preparation complete")
    logger.info(f"Duration: {result['duration_human']}")
    logger.info(f"Instance: {result['instance_id']}")
    
    return result


def prepare_500gb_dataset(fsx_file_system_id: str):
    """
    Prepare 500GB dataset (chr1-chr22, chrX)
    
    Args:
        fsx_file_system_id: FSx file system ID
    """
    logger.info("=" * 80)
    logger.info("Preparing 500GB Dataset")
    logger.info("=" * 80)
    
    orchestrator = DatasetPreparationOrchestrator(
        region="us-west-2",
        availability_zone="us-west-2a"
    )
    
    chromosomes = [f"chr{i}" for i in range(1, 23)] + ["chrX"]
    
    result = orchestrator.prepare_dataset(
        fsx_file_system_id=fsx_file_system_id,
        fsx_mount_name="/genomics",
        chromosomes=chromosomes,
        dest_subdir="phase_500gb",
        volume_size="500GB",
        auto_terminate=True,
        monitor_interval=120,
        max_runtime_hours=6
    )
    
    logger.info("500GB dataset preparation complete")
    logger.info(f"Duration: {result['duration_human']}")
    logger.info(f"Instance: {result['instance_id']}")
    
    return result


def prepare_all_datasets_sequentially(fsx_file_system_id: str):
    """
    Prepare all datasets sequentially (10GB → 100GB → 500GB)
    
    Args:
        fsx_file_system_id: FSx file system ID
    """
    logger.info("=" * 80)
    logger.info("Sequential Dataset Preparation")
    logger.info("Preparing: 10GB → 100GB → 500GB")
    logger.info("=" * 80)
    
    results = {}
    
    # Phase 1: 10GB
    try:
        results['10GB'] = prepare_10gb_dataset(fsx_file_system_id)
    except Exception as e:
        logger.error(f"10GB preparation failed: {e}")
        results['10GB'] = {'success': False, 'error': str(e)}
    
    # Phase 2: 100GB
    try:
        results['100GB'] = prepare_100gb_dataset(fsx_file_system_id)
    except Exception as e:
        logger.error(f"100GB preparation failed: {e}")
        results['100GB'] = {'success': False, 'error': str(e)}
    
    # Phase 3: 500GB
    try:
        results['500GB'] = prepare_500gb_dataset(fsx_file_system_id)
    except Exception as e:
        logger.error(f"500GB preparation failed: {e}")
        results['500GB'] = {'success': False, 'error': str(e)}
    
    # Summary
    logger.info("=" * 80)
    logger.info("All Dataset Preparation Complete")
    logger.info("=" * 80)
    
    for size, result in results.items():
        if result.get('success'):
            logger.info(f"{size}: ✓ Success ({result['duration_human']})")
        else:
            logger.info(f"{size}: ✗ Failed ({result.get('error', 'Unknown error')})")
    
    # Save results
    output_file = Path("dataset_preparation_results.json")
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Results saved to {output_file}")
    
    return results


def estimate_costs(dataset_size_gb: int, preparation_hours: float):
    """
    Estimate costs for EC2-based data preparation
    
    Args:
        dataset_size_gb: Dataset size in GB
        preparation_hours: Estimated preparation time in hours
        
    Returns:
        Dictionary with cost breakdown
    """
    # EC2 costs
    ec2_hourly_rate = 0.68  # c5.4xlarge on-demand
    ec2_cost = ec2_hourly_rate * preparation_hours
    
    # Cross-AZ transfer costs (alternative approach)
    cross_az_rate_per_gb = 0.01
    cross_az_cost = cross_az_rate_per_gb * dataset_size_gb
    
    # Savings
    savings = cross_az_cost - ec2_cost
    savings_percent = (savings / cross_az_cost * 100) if cross_az_cost > 0 else 0
    
    return {
        'dataset_size_gb': dataset_size_gb,
        'preparation_hours': preparation_hours,
        'ec2_cost_usd': round(ec2_cost, 2),
        'cross_az_cost_usd': round(cross_az_cost, 2),
        'savings_usd': round(savings, 2),
        'savings_percent': round(savings_percent, 1),
        'recommendation': 'Use EC2' if savings > 0 else 'Use direct transfer'
    }


def print_cost_comparison():
    """Print cost comparison for different dataset sizes"""
    logger.info("=" * 80)
    logger.info("Cost Comparison: EC2 vs Direct Cross-AZ Transfer")
    logger.info("=" * 80)
    
    datasets = [
        {'size_gb': 10, 'hours': 0.5},
        {'size_gb': 100, 'hours': 1.0},
        {'size_gb': 500, 'hours': 2.0},
        {'size_gb': 1024, 'hours': 3.0},
        {'size_gb': 2048, 'hours': 4.0}
    ]
    
    for dataset in datasets:
        costs = estimate_costs(dataset['size_gb'], dataset['hours'])
        
        logger.info(f"\n{costs['dataset_size_gb']}GB Dataset:")
        logger.info(f"  Preparation time: {costs['preparation_hours']} hours")
        logger.info(f"  EC2 cost: ${costs['ec2_cost_usd']}")
        logger.info(f"  Cross-AZ cost: ${costs['cross_az_cost_usd']}")
        logger.info(f"  Savings: ${costs['savings_usd']} ({costs['savings_percent']}%)")
        logger.info(f"  Recommendation: {costs['recommendation']}")


def main():
    """Main example workflow"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Example EC2 data preparation workflow"
    )
    parser.add_argument(
        '--fsx-file-system-id',
        help='FSx file system ID (required for actual preparation)'
    )
    parser.add_argument(
        '--dataset-size',
        choices=['10GB', '100GB', '500GB', 'all'],
        default='10GB',
        help='Dataset size to prepare'
    )
    parser.add_argument(
        '--cost-comparison',
        action='store_true',
        help='Print cost comparison and exit'
    )
    
    args = parser.parse_args()
    
    # Print cost comparison
    if args.cost_comparison:
        print_cost_comparison()
        return
    
    # Prepare datasets
    if not args.fsx_file_system_id:
        logger.error("--fsx-file-system-id is required for dataset preparation")
        logger.info("Use --cost-comparison to see cost estimates without preparing datasets")
        return
    
    if args.dataset_size == '10GB':
        prepare_10gb_dataset(args.fsx_file_system_id)
    elif args.dataset_size == '100GB':
        prepare_100gb_dataset(args.fsx_file_system_id)
    elif args.dataset_size == '500GB':
        prepare_500gb_dataset(args.fsx_file_system_id)
    elif args.dataset_size == 'all':
        prepare_all_datasets_sequentially(args.fsx_file_system_id)


if __name__ == "__main__":
    main()
