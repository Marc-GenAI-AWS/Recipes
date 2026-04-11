#!/usr/bin/env python3
"""
Example: Complete Data Validation Workflow

Demonstrates the complete workflow for downloading, uploading, and validating
hg38 chromosome data for cross-AZ FSx validation.

This example shows integration between:
- hg38_downloader: Download chromosome data
- checksum_calculator: Calculate and verify checksums
- fsx_uploader: Upload to FSx with integrity checks
- data_integrity_validator: Validate upload integrity

Usage:
    python example_validation_workflow.py --data-dir ./test_data --fsx-mount /mnt/fsx
"""

import argparse
import logging
import sys
from pathlib import Path

from hg38_downloader import HG38Downloader
from checksum_calculator import ChecksumCalculator
from fsx_uploader import FSxUploader
from data_integrity_validator import DataIntegrityValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_complete_workflow(
    data_dir: str,
    fsx_mount: str,
    chromosomes: list = None,
    dest_subdir: str = None
) -> bool:
    """
    Run complete data validation workflow
    
    Args:
        data_dir: Directory for downloaded data
        fsx_mount: FSx mount point
        chromosomes: List of chromosomes to download (default: chr21, chr22)
        dest_subdir: Optional subdirectory in FSx mount
        
    Returns:
        True if workflow completed successfully, False otherwise
    """
    if chromosomes is None:
        # Use smaller chromosomes for testing
        chromosomes = ["chr21", "chr22"]
    
    logger.info("=" * 80)
    logger.info("STARTING COMPLETE DATA VALIDATION WORKFLOW")
    logger.info("=" * 80)
    
    try:
        # Step 1: Download chromosome data
        logger.info("\n[STEP 1] Downloading chromosome data from UCSC")
        logger.info("-" * 80)
        
        downloader = HG38Downloader(output_dir=data_dir)
        download_results = downloader.download_chromosomes(chromosomes)
        
        failed_downloads = [r for r in download_results if r.get("status") == "failed"]
        if failed_downloads:
            logger.error(f"Failed to download {len(failed_downloads)} chromosomes")
            return False
        
        logger.info(f"✓ Successfully downloaded {len(chromosomes)} chromosomes")
        
        # Step 2: Calculate checksums
        logger.info("\n[STEP 2] Calculating checksums for downloaded files")
        logger.info("-" * 80)
        
        calculator = ChecksumCalculator(data_dir=data_dir)
        manifest = calculator.generate_manifest(pattern="*.fa.gz")
        manifest_path = calculator.save_manifest()
        
        logger.info(f"✓ Checksums calculated and saved to {manifest_path}")
        
        # Step 3: Upload to FSx
        logger.info("\n[STEP 3] Uploading data to FSx volume")
        logger.info("-" * 80)
        
        uploader = FSxUploader(
            source_dir=data_dir,
            fsx_mount_point=fsx_mount,
            verify_checksums=True,
            resume=True
        )
        
        # Verify FSx mount is accessible
        if not uploader.verify_mount_access():
            logger.error("FSx mount is not accessible")
            return False
        
        upload_result = uploader.upload_directory(
            pattern="*.fa.gz",
            dest_subdir=dest_subdir
        )
        
        if upload_result["failed_files"] > 0:
            logger.error(f"Failed to upload {upload_result['failed_files']} files")
            return False
        
        # Save upload manifest
        upload_manifest_path = uploader.save_upload_manifest(upload_result)
        logger.info(f"✓ Upload complete, manifest saved to {upload_manifest_path}")
        
        # Step 4: Validate upload integrity
        logger.info("\n[STEP 4] Validating upload integrity")
        logger.info("-" * 80)
        
        validator = DataIntegrityValidator(
            source_dir=data_dir,
            fsx_mount_path=fsx_mount,
            checksum_manifest_path=str(manifest_path)
        )
        
        validation_results = validator.validate_upload(
            dest_subdir=dest_subdir,
            pattern="*.fa.gz"
        )
        
        # Generate validation report
        report_path = validator.generate_validation_report(validation_results)
        logger.info(f"✓ Validation report saved to {report_path}")
        
        # Step 5: Summary
        logger.info("\n" + "=" * 80)
        logger.info("WORKFLOW SUMMARY")
        logger.info("=" * 80)
        
        logger.info(f"Downloaded:  {len(chromosomes)} chromosomes")
        logger.info(f"Uploaded:    {upload_result['uploaded_files']} files")
        logger.info(f"Skipped:     {upload_result['skipped_files']} files")
        logger.info(f"Validated:   {validation_results['valid_files']}/{validation_results['total_files']} files")
        logger.info(f"Total Size:  {validator._format_size(validation_results['total_size_bytes'])}")
        
        if validation_results["invalid_files"] > 0:
            logger.error(f"\n✗ WORKFLOW FAILED: {validation_results['invalid_files']} files failed validation")
            logger.error("Check validation report for details")
            return False
        
        logger.info("\n✓ WORKFLOW COMPLETED SUCCESSFULLY")
        logger.info("All files downloaded, uploaded, and validated successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"\n✗ WORKFLOW FAILED: {e}")
        return False


def main():
    """Command-line interface for the workflow"""
    parser = argparse.ArgumentParser(
        description="Run complete data validation workflow"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        required=True,
        help="Directory for downloaded data"
    )
    parser.add_argument(
        "--fsx-mount",
        type=str,
        required=True,
        help="FSx volume mount point (e.g., /mnt/fsx)"
    )
    parser.add_argument(
        "--chromosomes",
        type=str,
        nargs="+",
        default=["chr21", "chr22"],
        help="Chromosomes to download (default: chr21 chr22)"
    )
    parser.add_argument(
        "--dest-subdir",
        type=str,
        help="Optional subdirectory within FSx mount point"
    )
    
    args = parser.parse_args()
    
    success = run_complete_workflow(
        data_dir=args.data_dir,
        fsx_mount=args.fsx_mount,
        chromosomes=args.chromosomes,
        dest_subdir=args.dest_subdir
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
