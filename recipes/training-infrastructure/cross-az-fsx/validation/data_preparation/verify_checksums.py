#!/usr/bin/env python3
"""
Verification script to demonstrate checksum calculator usage

This script shows how to use the checksum calculator with downloaded
chromosome files for data integrity validation.
"""

import argparse
import logging
import sys
from pathlib import Path
from checksum_calculator import ChecksumCalculator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Verify checksums for downloaded chromosome files"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="./hg38_data",
        help="Directory containing chromosome files (default: ./hg38_data)"
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate new manifest before verification"
    )
    
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir)
    
    if not data_dir.exists():
        logger.error(f"Data directory does not exist: {data_dir}")
        sys.exit(1)
    
    try:
        calculator = ChecksumCalculator(str(data_dir))
        
        # Generate manifest if requested
        if args.generate:
            logger.info("Generating checksum manifest...")
            manifest = calculator.generate_manifest()
            calculator.save_manifest(manifest)
            
            metadata = manifest['metadata']
            logger.info(f"✓ Generated manifest with {metadata['successful_files']} files")
            logger.info(f"  Total size: {metadata['total_size_human']}")
            
            if metadata['failed_files'] > 0:
                logger.warning(f"  {metadata['failed_files']} files failed")
        
        # Verify all files
        logger.info("Verifying file integrity...")
        results = calculator.verify_all_files()
        
        # Report results
        passed = sum(1 for v in results.values() if v)
        failed = len(results) - passed
        
        print("\n" + "="*60)
        print("VERIFICATION RESULTS")
        print("="*60)
        
        for filename, is_valid in sorted(results.items()):
            status = "✓ PASS" if is_valid else "✗ FAIL"
            print(f"{status:8} {filename}")
        
        print("="*60)
        print(f"Total: {len(results)} files")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print("="*60)
        
        if failed > 0:
            logger.error(f"{failed} file(s) failed verification")
            sys.exit(1)
        else:
            logger.info("All files verified successfully")
            sys.exit(0)
    
    except FileNotFoundError as e:
        logger.error(f"Manifest not found. Run with --generate to create one.")
        logger.error(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
