#!/usr/bin/env python3
"""
Prepare datasets for cross-AZ FSx validation phases

This script prepares the hg38 chromosome datasets for each validation phase:
- Phase 2.5: 10GB (chr1, chr2)
- Phase 2.6: 100GB (chr1-chr10)
- Phase 2.7: 500GB (chr1-chr22, chrX)
- Phase 2.8: 1TB (all chromosomes)
- Phase 2.9: 2TB (all chromosomes with variants)
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List

from hg38_downloader import HG38Downloader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Dataset configurations for each validation phase
PHASE_CONFIGS = {
    "10GB": {
        "chromosomes": ["chr1", "chr2"],
        "description": "Phase 2.5: 10GB validation dataset"
    },
    "100GB": {
        "chromosomes": [f"chr{i}" for i in range(1, 11)],
        "description": "Phase 2.6: 100GB validation dataset"
    },
    "500GB": {
        "chromosomes": [f"chr{i}" for i in range(1, 23)] + ["chrX"],
        "description": "Phase 2.7: 500GB validation dataset"
    },
    "1TB": {
        "chromosomes": [f"chr{i}" for i in range(1, 23)] + ["chrX", "chrY", "chrM"],
        "description": "Phase 2.8: 1TB validation dataset (all chromosomes)"
    },
    "2TB": {
        "chromosomes": [f"chr{i}" for i in range(1, 23)] + ["chrX", "chrY", "chrM"],
        "description": "Phase 2.9: 2TB validation dataset (all chromosomes, will need duplication)"
    }
}


def prepare_phase_dataset(
    phase: str,
    base_output_dir: str,
    force: bool = False
) -> Dict:
    """
    Prepare dataset for a specific validation phase
    
    Args:
        phase: Phase identifier (10GB, 100GB, 500GB, 1TB, 2TB)
        base_output_dir: Base directory for all datasets
        force: Force re-download of existing files
        
    Returns:
        Dictionary with phase preparation results
    """
    if phase not in PHASE_CONFIGS:
        raise ValueError(f"Unknown phase: {phase}. Valid phases: {list(PHASE_CONFIGS.keys())}")
    
    config = PHASE_CONFIGS[phase]
    phase_dir = Path(base_output_dir) / phase.lower()
    
    logger.info(f"Preparing {phase} dataset: {config['description']}")
    logger.info(f"Output directory: {phase_dir}")
    logger.info(f"Chromosomes: {', '.join(config['chromosomes'])}")
    
    # Initialize downloader
    downloader = HG38Downloader(
        output_dir=str(phase_dir),
        max_retries=3,
        retry_delay=5,
        timeout=600  # 10 minutes per file
    )
    
    # Download chromosomes
    results = downloader.download_chromosomes(
        chromosomes=config['chromosomes'],
        force=force
    )
    
    # Calculate statistics
    total_size = sum(r.get('size_bytes', 0) for r in results if r.get('status') != 'failed')
    successful = sum(1 for r in results if r.get('status') in ['downloaded', 'skipped'])
    failed = sum(1 for r in results if r.get('status') == 'failed')
    
    phase_result = {
        "phase": phase,
        "description": config['description'],
        "output_dir": str(phase_dir),
        "chromosomes": config['chromosomes'],
        "total_chromosomes": len(config['chromosomes']),
        "successful_downloads": successful,
        "failed_downloads": failed,
        "total_size_bytes": total_size,
        "total_size_gb": round(total_size / (1024**3), 2),
        "download_results": results
    }
    
    logger.info(f"Phase {phase} preparation complete:")
    logger.info(f"  - Successful: {successful}/{len(config['chromosomes'])}")
    logger.info(f"  - Failed: {failed}")
    logger.info(f"  - Total size: {phase_result['total_size_gb']} GB")
    
    return phase_result


def prepare_all_phases(
    base_output_dir: str,
    phases: List[str] = None,
    force: bool = False
) -> Dict:
    """
    Prepare datasets for multiple validation phases
    
    Args:
        base_output_dir: Base directory for all datasets
        phases: List of phases to prepare (default: all phases)
        force: Force re-download of existing files
        
    Returns:
        Dictionary with all phase results
    """
    if phases is None:
        phases = list(PHASE_CONFIGS.keys())
    
    logger.info(f"Preparing datasets for phases: {', '.join(phases)}")
    
    all_results = {
        "base_output_dir": base_output_dir,
        "phases": {}
    }
    
    for phase in phases:
        try:
            phase_result = prepare_phase_dataset(phase, base_output_dir, force)
            all_results["phases"][phase] = phase_result
            
            # Save phase metadata
            metadata_file = Path(base_output_dir) / phase.lower() / "metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(phase_result, f, indent=2)
            logger.info(f"Saved metadata to {metadata_file}")
            
        except Exception as e:
            logger.error(f"Failed to prepare phase {phase}: {e}")
            all_results["phases"][phase] = {
                "phase": phase,
                "status": "failed",
                "error": str(e)
            }
    
    # Save overall summary
    summary_file = Path(base_output_dir) / "preparation_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    logger.info(f"Saved preparation summary to {summary_file}")
    
    return all_results


def main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(
        description="Prepare hg38 datasets for cross-AZ FSx validation phases"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./validation_datasets",
        help="Base output directory for all datasets (default: ./validation_datasets)"
    )
    parser.add_argument(
        "--phases",
        type=str,
        nargs="+",
        choices=list(PHASE_CONFIGS.keys()),
        help="Specific phases to prepare (default: all phases)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if files exist"
    )
    parser.add_argument(
        "--list-phases",
        action="store_true",
        help="List available phases and exit"
    )
    
    args = parser.parse_args()
    
    # List phases if requested
    if args.list_phases:
        print("\nAvailable validation phases:")
        print("-" * 80)
        for phase, config in PHASE_CONFIGS.items():
            print(f"\n{phase}:")
            print(f"  Description: {config['description']}")
            print(f"  Chromosomes: {', '.join(config['chromosomes'])}")
            print(f"  Count: {len(config['chromosomes'])} chromosomes")
        print()
        sys.exit(0)
    
    # Prepare datasets
    try:
        results = prepare_all_phases(
            base_output_dir=args.output_dir,
            phases=args.phases,
            force=args.force
        )
        
        # Check for failures
        failed_phases = [
            phase for phase, result in results["phases"].items()
            if result.get("status") == "failed" or result.get("failed_downloads", 0) > 0
        ]
        
        if failed_phases:
            logger.error(f"Some phases had failures: {', '.join(failed_phases)}")
            sys.exit(1)
        else:
            logger.info("All phases prepared successfully")
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
