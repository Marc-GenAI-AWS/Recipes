#!/usr/bin/env python3
"""
hg38 Chromosome Data Downloader from UCSC

Downloads hg38 chromosome data from UCSC Genome Browser for use in
cross-AZ FSx validation testing with BioNeMo Megatron Framework.

Data source: https://hgdownload.soe.ucsc.edu/goldenpath/hg38/chromosomes/
"""

import argparse
import hashlib
import logging
import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Dict
from urllib.parse import urljoin
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# UCSC hg38 chromosome data URL
UCSC_HG38_BASE_URL = "https://hgdownload.soe.ucsc.edu/goldenpath/hg38/chromosomes/"

# All human chromosomes
ALL_CHROMOSOMES = [
    f"chr{i}" for i in range(1, 23)
] + ["chrX", "chrY", "chrM"]


class DownloadError(Exception):
    """Custom exception for download errors"""
    pass


class HG38Downloader:
    """Downloads hg38 chromosome data from UCSC with retry logic"""
    
    def __init__(
        self,
        output_dir: str,
        max_retries: int = 3,
        retry_delay: int = 5,
        timeout: int = 300
    ):
        """
        Initialize the downloader
        
        Args:
            output_dir: Directory to save downloaded files
            max_retries: Maximum number of retry attempts for failed downloads
            retry_delay: Delay in seconds between retries
            timeout: Timeout in seconds for each download request
        """
        self.output_dir = Path(output_dir)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized HG38Downloader with output_dir={output_dir}")
    
    def download_chromosome(
        self,
        chromosome: str,
        force: bool = False
    ) -> Dict[str, any]:
        """
        Download a single chromosome file
        
        Args:
            chromosome: Chromosome name (e.g., 'chr1', 'chrX')
            force: If True, re-download even if file exists
            
        Returns:
            Dictionary with download metadata:
                - chromosome: Chromosome name
                - filename: Downloaded filename
                - filepath: Full path to downloaded file
                - size_bytes: File size in bytes
                - download_time_seconds: Time taken to download
                - checksum_md5: MD5 checksum of downloaded file
                
        Raises:
            DownloadError: If download fails after all retries
        """
        filename = f"{chromosome}.fa.gz"
        filepath = self.output_dir / filename
        url = urljoin(UCSC_HG38_BASE_URL, filename)
        
        # Check if file already exists
        if filepath.exists() and not force:
            logger.info(f"{filename} already exists, skipping download")
            file_size = filepath.stat().st_size
            checksum = self._calculate_md5(filepath)
            return {
                "chromosome": chromosome,
                "filename": filename,
                "filepath": str(filepath),
                "size_bytes": file_size,
                "download_time_seconds": 0,
                "checksum_md5": checksum,
                "status": "skipped"
            }
        
        # Download with retry logic
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Downloading {filename} (attempt {attempt}/{self.max_retries})")
                start_time = time.time()
                
                # Download file
                self._download_file(url, filepath)
                
                download_time = time.time() - start_time
                file_size = filepath.stat().st_size
                
                # Calculate checksum
                logger.info(f"Calculating MD5 checksum for {filename}")
                checksum = self._calculate_md5(filepath)
                
                logger.info(
                    f"Successfully downloaded {filename} "
                    f"({self._format_size(file_size)}) in {download_time:.2f}s"
                )
                
                return {
                    "chromosome": chromosome,
                    "filename": filename,
                    "filepath": str(filepath),
                    "size_bytes": file_size,
                    "download_time_seconds": download_time,
                    "checksum_md5": checksum,
                    "status": "downloaded"
                }
                
            except (URLError, HTTPError, IOError) as e:
                logger.error(f"Download attempt {attempt} failed: {e}")
                
                # Clean up partial download
                if filepath.exists():
                    filepath.unlink()
                
                if attempt < self.max_retries:
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    raise DownloadError(
                        f"Failed to download {filename} after {self.max_retries} attempts"
                    ) from e
    
    def download_chromosomes(
        self,
        chromosomes: List[str],
        force: bool = False
    ) -> List[Dict[str, any]]:
        """
        Download multiple chromosomes
        
        Args:
            chromosomes: List of chromosome names to download
            force: If True, re-download even if files exist
            
        Returns:
            List of download metadata dictionaries
        """
        results = []
        total_size = 0
        total_time = 0
        
        logger.info(f"Starting download of {len(chromosomes)} chromosomes")
        
        for i, chromosome in enumerate(chromosomes, 1):
            logger.info(f"Processing chromosome {i}/{len(chromosomes)}: {chromosome}")
            
            try:
                result = self.download_chromosome(chromosome, force=force)
                results.append(result)
                total_size += result["size_bytes"]
                total_time += result["download_time_seconds"]
                
            except DownloadError as e:
                logger.error(f"Failed to download {chromosome}: {e}")
                results.append({
                    "chromosome": chromosome,
                    "status": "failed",
                    "error": str(e)
                })
        
        # Summary
        successful = sum(1 for r in results if r.get("status") in ["downloaded", "skipped"])
        failed = len(results) - successful
        
        logger.info(
            f"Download complete: {successful} successful, {failed} failed, "
            f"total size: {self._format_size(total_size)}, "
            f"total time: {total_time:.2f}s"
        )
        
        return results
    
    def download_all_chromosomes(self, force: bool = False) -> List[Dict[str, any]]:
        """
        Download all human chromosomes
        
        Args:
            force: If True, re-download even if files exist
            
        Returns:
            List of download metadata dictionaries
        """
        return self.download_chromosomes(ALL_CHROMOSOMES, force=force)
    
    def _download_file(self, url: str, filepath: Path) -> None:
        """
        Download a file from URL to filepath with progress tracking
        
        Args:
            url: URL to download from
            filepath: Path to save the file
            
        Raises:
            URLError, HTTPError: On network errors
        """
        request = Request(url)
        request.add_header('User-Agent', 'HG38Downloader/1.0')
        
        with urlopen(request, timeout=self.timeout) as response:
            total_size = int(response.headers.get('Content-Length', 0))
            
            with open(filepath, 'wb') as f:
                downloaded = 0
                chunk_size = 8192
                last_progress = 0
                
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # Log progress every 10%
                    if total_size > 0:
                        progress = int((downloaded / total_size) * 100)
                        if progress >= last_progress + 10:
                            logger.info(
                                f"Progress: {progress}% "
                                f"({self._format_size(downloaded)}/{self._format_size(total_size)})"
                            )
                            last_progress = progress
    
    def _calculate_md5(self, filepath: Path) -> str:
        """
        Calculate MD5 checksum of a file
        
        Args:
            filepath: Path to the file
            
        Returns:
            MD5 checksum as hex string
        """
        md5_hash = hashlib.md5()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    
    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format byte size as human-readable string"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"


def main():
    """Command-line interface for the downloader"""
    parser = argparse.ArgumentParser(
        description="Download hg38 chromosome data from UCSC Genome Browser"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./hg38_data",
        help="Output directory for downloaded files (default: ./hg38_data)"
    )
    parser.add_argument(
        "--chromosomes",
        type=str,
        nargs="+",
        help="Specific chromosomes to download (e.g., chr1 chr2 chrX). If not specified, downloads all."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if files exist"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum number of retry attempts (default: 3)"
    )
    parser.add_argument(
        "--retry-delay",
        type=int,
        default=5,
        help="Delay in seconds between retries (default: 5)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Timeout in seconds for each download (default: 300)"
    )
    
    args = parser.parse_args()
    
    # Initialize downloader
    downloader = HG38Downloader(
        output_dir=args.output_dir,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
        timeout=args.timeout
    )
    
    # Download chromosomes
    try:
        if args.chromosomes:
            results = downloader.download_chromosomes(args.chromosomes, force=args.force)
        else:
            results = downloader.download_all_chromosomes(force=args.force)
        
        # Check for failures
        failed = [r for r in results if r.get("status") == "failed"]
        if failed:
            logger.error(f"{len(failed)} downloads failed")
            sys.exit(1)
        else:
            logger.info("All downloads completed successfully")
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
