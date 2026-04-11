#!/usr/bin/env python3
"""
Example: Integration of hg38_downloader with checksum_calculator

This example demonstrates the recommended workflow for downloading
and validating chromosome files for the cross-AZ FSx validation.
"""

from hg38_downloader import HG38Downloader
from checksum_calculator import ChecksumCalculator
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def download_and_validate_chromosomes(
    chromosomes: list,
    output_dir: str = "./hg38_data"
):
    """
    Download chromosomes and generate checksum manifest
    
    Args:
        chromosomes: List of chromosome names to download (e.g., ['chr1', 'chr2'])
        output_dir: Directory to save downloaded files
        
    Returns:
        Tuple of (download_results, manifest)
    """
    
    logger.info("="*70)
    logger.info("CHROMOSOME DOWNLOAD AND VALIDATION WORKFLOW")
    logger.info("="*70)
    
    # Step 1: Download chromosomes
    logger.info(f"Step 1: Downloading {len(chromosomes)} chromosomes...")
    downloader = HG38Downloader(output_dir=output_dir)
    download_results = downloader.download_chromosomes(chromosomes)
    
    # Check download results
    successful_downloads = [r for r in download_results if r.get('status') in ['downloaded', 'skipped']]
    failed_downloads = [r for r in download_results if r.get('status') == 'failed']
    
    logger.info(f"  Downloaded: {len(successful_downloads)} files")
    if failed_downloads:
        logger.warning(f"  Failed: {len(failed_downloads)} files")
        for result in failed_downloads:
            logger.warning(f"    - {result['chromosome']}: {result.get('error', 'Unknown error')}")
    
    # Step 2: Generate checksum manifest
    logger.info("Step 2: Generating checksum manifest...")
    calculator = ChecksumCalculator(data_dir=output_dir)
    manifest = calculator.generate_manifest()
    manifest_path = calculator.save_manifest(manifest)
    
    metadata = manifest['metadata']
    logger.info(f"  Manifest saved: {manifest_path}")
    logger.info(f"  Files: {metadata['successful_files']}")
    logger.info(f"  Total size: {metadata['total_size_human']}")
    
    # Step 3: Verify integrity
    logger.info("Step 3: Verifying file integrity...")
    verification_results = calculator.verify_all_files()
    
    passed = sum(1 for v in verification_results.values() if v)
    failed = len(verification_results) - passed
    
    logger.info(f"  Verified: {passed} files passed")
    if failed > 0:
        logger.error(f"  Failed: {failed} files failed verification")
        for filename, is_valid in verification_results.items():
            if not is_valid:
                logger.error(f"    - {filename}")
    
    # Step 4: Compare checksums
    logger.info("Step 4: Comparing checksums...")
    logger.info("  Note: hg38_downloader calculates MD5, checksum_calculator adds SHA256")
    
    for result in download_results:
        if result.get('status') in ['downloaded', 'skipped']:
            filename = result['filename']
            downloader_md5 = result.get('checksum_md5')
            manifest_md5 = manifest['files'][filename]['md5']
            
            if downloader_md5 == manifest_md5:
                logger.info(f"  ✓ {filename}: MD5 checksums match")
            else:
                logger.error(f"  ✗ {filename}: MD5 checksums DO NOT match")
    
    logger.info("="*70)
    logger.info("WORKFLOW COMPLETE")
    logger.info("="*70)
    
    return download_results, manifest


def main():
    """Example usage"""
    
    # Example 1: Download and validate a small dataset (10GB phase)
    logger.info("\nExample 1: 10GB Dataset (chr1, chr2)")
    logger.info("-" * 70)
    
    # Note: This is a demonstration. Actual download would be:
    # download_and_validate_chromosomes(['chr1', 'chr2'], './hg38_data_10gb')
    
    logger.info("To download and validate chr1 and chr2:")
    logger.info("  download_results, manifest = download_and_validate_chromosomes(")
    logger.info("      chromosomes=['chr1', 'chr2'],")
    logger.info("      output_dir='./hg38_data_10gb'")
    logger.info("  )")
    
    # Example 2: Verify existing files
    logger.info("\nExample 2: Verify Existing Files")
    logger.info("-" * 70)
    
    logger.info("To verify files after transfer to FSx:")
    logger.info("  calculator = ChecksumCalculator(data_dir='/mnt/fsx/hg38_data')")
    logger.info("  results = calculator.verify_all_files()")
    logger.info("  if all(results.values()):")
    logger.info("      print('All files verified successfully')")
    
    # Example 3: Detect corruption
    logger.info("\nExample 3: Detect Corruption During Transfer")
    logger.info("-" * 70)
    
    logger.info("To detect corruption during transfer:")
    logger.info("  # Before transfer")
    logger.info("  calc_source = ChecksumCalculator(data_dir='./hg38_data')")
    logger.info("  manifest_source = calc_source.generate_manifest()")
    logger.info("  ")
    logger.info("  # After transfer to FSx")
    logger.info("  calc_dest = ChecksumCalculator(data_dir='/mnt/fsx/hg38_data')")
    logger.info("  results = calc_dest.verify_all_files(manifest=manifest_source)")
    logger.info("  ")
    logger.info("  # Check for corruption")
    logger.info("  corrupted = [f for f, v in results.items() if not v]")
    logger.info("  if corrupted:")
    logger.info("      print(f'Corrupted files: {corrupted}')")


if __name__ == "__main__":
    main()
