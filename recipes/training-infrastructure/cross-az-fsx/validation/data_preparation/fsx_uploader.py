#!/usr/bin/env python3
"""
FSx Volume Data Uploader

Uploads downloaded hg38 chromosome data to FSx NetApp ONTAP volume with:
- Progress tracking
- Error handling and retry logic
- Checksum verification for upload integrity
- Support for resuming interrupted uploads
"""

import argparse
import hashlib
import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UploadError(Exception):
    """Custom exception for upload errors"""
    pass


class FSxUploader:
    """Uploads chromosome data to FSx volume with integrity verification"""
    
    def __init__(
        self,
        source_dir: str,
        fsx_mount_point: str,
        max_retries: int = 3,
        retry_delay: int = 5,
        verify_checksums: bool = True,
        resume: bool = True
    ):
        """
        Initialize the FSx uploader
        
        Args:
            source_dir: Directory containing files to upload
            fsx_mount_point: Mount point of FSx volume (e.g., /mnt/fsx)
            max_retries: Maximum number of retry attempts for failed uploads
            retry_delay: Delay in seconds between retries
            verify_checksums: Verify upload integrity using checksums
            resume: Skip files that already exist with matching checksums
        """
        self.source_dir = Path(source_dir)
        self.fsx_mount_point = Path(fsx_mount_point)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.verify_checksums = verify_checksums
        self.resume = resume
        
        # Validate source directory
        if not self.source_dir.exists():
            raise ValueError(f"Source directory does not exist: {source_dir}")
        
        # Validate FSx mount point
        if not self.fsx_mount_point.exists():
            raise ValueError(f"FSx mount point does not exist: {fsx_mount_point}")
        
        # Check if it's a mount point (only on systems that support it)
        try:
            if not self.fsx_mount_point.is_mount():
                logger.warning(
                    f"{fsx_mount_point} does not appear to be a mount point. "
                    "Ensure FSx volume is properly mounted."
                )
        except NotImplementedError:
            # is_mount() not supported on this system (e.g., Windows)
            logger.debug(f"Mount point check not supported on this system")
        
        logger.info(f"Initialized FSxUploader")
        logger.info(f"  Source: {source_dir}")
        logger.info(f"  Destination: {fsx_mount_point}")
        logger.info(f"  Verify checksums: {verify_checksums}")
        logger.info(f"  Resume: {resume}")
    
    def verify_mount_access(self) -> bool:
        """
        Verify FSx mount is accessible and writable
        
        Returns:
            True if mount is accessible and writable
        """
        try:
            # Test read access
            if not os.access(self.fsx_mount_point, os.R_OK):
                logger.error(f"FSx mount point is not readable: {self.fsx_mount_point}")
                return False
            
            # Test write access
            if not os.access(self.fsx_mount_point, os.W_OK):
                logger.error(f"FSx mount point is not writable: {self.fsx_mount_point}")
                return False
            
            # Test by creating a temporary file
            test_file = self.fsx_mount_point / ".upload_test"
            try:
                test_file.write_text("test")
                test_file.unlink()
                logger.info("FSx mount access verified successfully")
                return True
            except Exception as e:
                logger.error(f"Failed to write test file to FSx mount: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error verifying FSx mount access: {e}")
            return False

    def calculate_checksum(self, filepath: Path, algorithm: str = 'md5') -> str:
        """
        Calculate checksum for a file
        
        Args:
            filepath: Path to the file
            algorithm: Hash algorithm ('md5' or 'sha256')
            
        Returns:
            Checksum as hex string
        """
        if algorithm == 'md5':
            hash_obj = hashlib.md5()
        elif algorithm == 'sha256':
            hash_obj = hashlib.sha256()
        else:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")
        
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hash_obj.update(chunk)
        
        return hash_obj.hexdigest()
    
    def should_skip_file(
        self,
        source_file: Path,
        dest_file: Path
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if file should be skipped (already uploaded)
        
        Args:
            source_file: Source file path
            dest_file: Destination file path
            
        Returns:
            Tuple of (should_skip, reason)
        """
        if not self.resume:
            return False, None
        
        if not dest_file.exists():
            return False, None
        
        # Check file size
        source_size = source_file.stat().st_size
        dest_size = dest_file.stat().st_size
        
        if source_size != dest_size:
            return False, f"size mismatch (source: {source_size}, dest: {dest_size})"
        
        # Verify checksums if enabled
        if self.verify_checksums:
            logger.info(f"Verifying existing file: {dest_file.name}")
            source_checksum = self.calculate_checksum(source_file)
            dest_checksum = self.calculate_checksum(dest_file)
            
            if source_checksum != dest_checksum:
                return False, f"checksum mismatch"
            
            return True, "file exists with matching checksum"
        
        return True, "file exists with matching size"
    
    def upload_file(
        self,
        source_file: Path,
        dest_subdir: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Upload a single file to FSx volume
        
        Args:
            source_file: Path to source file
            dest_subdir: Optional subdirectory within FSx mount point
            
        Returns:
            Dictionary with upload metadata:
                - filename: Name of the file
                - source_path: Source file path
                - dest_path: Destination file path
                - size_bytes: File size
                - upload_time_seconds: Time taken to upload
                - checksum_source: Source file checksum (if verification enabled)
                - checksum_dest: Destination file checksum (if verification enabled)
                - status: 'uploaded', 'skipped', or 'failed'
                
        Raises:
            UploadError: If upload fails after all retries
        """
        filename = source_file.name
        
        # Determine destination path
        if dest_subdir:
            dest_dir = self.fsx_mount_point / dest_subdir
            dest_dir.mkdir(parents=True, exist_ok=True)
        else:
            dest_dir = self.fsx_mount_point
        
        dest_file = dest_dir / filename
        
        # Check if file should be skipped
        should_skip, skip_reason = self.should_skip_file(source_file, dest_file)
        if should_skip:
            logger.info(f"{filename} already exists, skipping ({skip_reason})")
            file_size = source_file.stat().st_size
            return {
                "filename": filename,
                "source_path": str(source_file),
                "dest_path": str(dest_file),
                "size_bytes": file_size,
                "upload_time_seconds": 0,
                "status": "skipped",
                "skip_reason": skip_reason
            }
        
        # Upload with retry logic
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Uploading {filename} (attempt {attempt}/{self.max_retries})")
                start_time = time.time()
                
                # Calculate source checksum before upload
                source_checksum = None
                if self.verify_checksums:
                    logger.info(f"Calculating source checksum for {filename}")
                    source_checksum = self.calculate_checksum(source_file)
                
                # Copy file with progress tracking
                file_size = source_file.stat().st_size
                self._copy_with_progress(source_file, dest_file, file_size)
                
                upload_time = time.time() - start_time
                
                # Verify upload integrity
                dest_checksum = None
                if self.verify_checksums:
                    logger.info(f"Verifying upload integrity for {filename}")
                    dest_checksum = self.calculate_checksum(dest_file)
                    
                    if source_checksum != dest_checksum:
                        raise UploadError(
                            f"Checksum mismatch after upload: "
                            f"source={source_checksum}, dest={dest_checksum}"
                        )
                    
                    logger.info(f"✓ Upload integrity verified for {filename}")
                
                logger.info(
                    f"Successfully uploaded {filename} "
                    f"({self._format_size(file_size)}) in {upload_time:.2f}s "
                    f"({self._format_rate(file_size, upload_time)})"
                )
                
                return {
                    "filename": filename,
                    "source_path": str(source_file),
                    "dest_path": str(dest_file),
                    "size_bytes": file_size,
                    "upload_time_seconds": upload_time,
                    "checksum_source": source_checksum,
                    "checksum_dest": dest_checksum,
                    "status": "uploaded"
                }
                
            except Exception as e:
                logger.error(f"Upload attempt {attempt} failed: {e}")
                
                # Clean up partial upload
                if dest_file.exists():
                    try:
                        dest_file.unlink()
                    except Exception as cleanup_error:
                        logger.error(f"Failed to clean up partial upload: {cleanup_error}")
                
                if attempt < self.max_retries:
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    raise UploadError(
                        f"Failed to upload {filename} after {self.max_retries} attempts"
                    ) from e
    
    def _copy_with_progress(
        self,
        source: Path,
        dest: Path,
        total_size: int
    ) -> None:
        """
        Copy file with progress logging
        
        Args:
            source: Source file path
            dest: Destination file path
            total_size: Total file size in bytes
        """
        copied = 0
        last_progress = 0
        chunk_size = 1024 * 1024  # 1 MB chunks
        
        with open(source, 'rb') as src, open(dest, 'wb') as dst:
            while True:
                chunk = src.read(chunk_size)
                if not chunk:
                    break
                
                dst.write(chunk)
                copied += len(chunk)
                
                # Log progress every 10%
                if total_size > 0:
                    progress = int((copied / total_size) * 100)
                    if progress >= last_progress + 10:
                        logger.info(
                            f"Progress: {progress}% "
                            f"({self._format_size(copied)}/{self._format_size(total_size)})"
                        )
                        last_progress = progress
    
    def upload_directory(
        self,
        pattern: str = "*.fa.gz",
        dest_subdir: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Upload all matching files from source directory to FSx volume
        
        Args:
            pattern: Glob pattern for files to upload (default: *.fa.gz)
            dest_subdir: Optional subdirectory within FSx mount point
            
        Returns:
            Dictionary with upload summary:
                - files: List of individual file upload results
                - total_files: Total number of files processed
                - uploaded_files: Number of files uploaded
                - skipped_files: Number of files skipped
                - failed_files: Number of files failed
                - total_size_bytes: Total size of uploaded data
                - total_time_seconds: Total upload time
        """
        files = list(self.source_dir.glob(pattern))
        
        if not files:
            logger.warning(f"No files matching pattern '{pattern}' found in {self.source_dir}")
            return {
                "files": [],
                "total_files": 0,
                "uploaded_files": 0,
                "skipped_files": 0,
                "failed_files": 0,
                "total_size_bytes": 0,
                "total_time_seconds": 0
            }
        
        logger.info(f"Found {len(files)} files matching pattern '{pattern}'")
        
        results = []
        total_size = 0
        total_time = 0
        uploaded_count = 0
        skipped_count = 0
        failed_count = 0
        
        for i, filepath in enumerate(sorted(files), 1):
            logger.info(f"Processing file {i}/{len(files)}: {filepath.name}")
            
            try:
                result = self.upload_file(filepath, dest_subdir)
                results.append(result)
                
                if result["status"] == "uploaded":
                    uploaded_count += 1
                    total_size += result["size_bytes"]
                    total_time += result["upload_time_seconds"]
                elif result["status"] == "skipped":
                    skipped_count += 1
                    total_size += result["size_bytes"]
                
            except UploadError as e:
                logger.error(f"Failed to upload {filepath.name}: {e}")
                failed_count += 1
                results.append({
                    "filename": filepath.name,
                    "source_path": str(filepath),
                    "status": "failed",
                    "error": str(e)
                })
        
        # Summary
        logger.info(f"Upload complete:")
        logger.info(f"  - Total files: {len(files)}")
        logger.info(f"  - Uploaded: {uploaded_count}")
        logger.info(f"  - Skipped: {skipped_count}")
        logger.info(f"  - Failed: {failed_count}")
        logger.info(f"  - Total size: {self._format_size(total_size)}")
        logger.info(f"  - Total time: {total_time:.2f}s")
        if total_time > 0:
            logger.info(f"  - Average rate: {self._format_rate(total_size, total_time)}")
        
        return {
            "files": results,
            "total_files": len(files),
            "uploaded_files": uploaded_count,
            "skipped_files": skipped_count,
            "failed_files": failed_count,
            "total_size_bytes": total_size,
            "total_time_seconds": total_time,
            "dest_subdir": dest_subdir
        }

    def save_upload_manifest(
        self,
        upload_result: Dict[str, any],
        manifest_path: Optional[str] = None
    ) -> Path:
        """
        Save upload manifest to file
        
        Args:
            upload_result: Result from upload_directory
            manifest_path: Path to save manifest (default: fsx_mount/upload_manifest.json)
            
        Returns:
            Path to saved manifest file
        """
        if manifest_path:
            manifest_file = Path(manifest_path)
        else:
            manifest_file = self.fsx_mount_point / "upload_manifest.json"
        
        manifest = {
            "uploaded_at": datetime.utcnow().isoformat() + 'Z',
            "source_dir": str(self.source_dir),
            "fsx_mount_point": str(self.fsx_mount_point),
            "summary": {
                "total_files": upload_result["total_files"],
                "uploaded_files": upload_result["uploaded_files"],
                "skipped_files": upload_result["skipped_files"],
                "failed_files": upload_result["failed_files"],
                "total_size_bytes": upload_result["total_size_bytes"],
                "total_size_human": self._format_size(upload_result["total_size_bytes"]),
                "total_time_seconds": upload_result["total_time_seconds"]
            },
            "files": upload_result["files"]
        }
        
        logger.info(f"Saving upload manifest to {manifest_file}")
        
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        logger.info("Upload manifest saved successfully")
        
        return manifest_file
    
    def verify_uploaded_files(
        self,
        manifest_path: Optional[str] = None
    ) -> Dict[str, bool]:
        """
        Verify integrity of uploaded files against manifest
        
        Args:
            manifest_path: Path to manifest file (default: fsx_mount/upload_manifest.json)
            
        Returns:
            Dictionary mapping filename to verification result (True/False)
        """
        if manifest_path:
            manifest_file = Path(manifest_path)
        else:
            manifest_file = self.fsx_mount_point / "upload_manifest.json"
        
        if not manifest_file.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_file}")
        
        logger.info(f"Loading manifest from {manifest_file}")
        
        with open(manifest_file, 'r') as f:
            manifest = json.load(f)
        
        results = {}
        
        for file_info in manifest["files"]:
            if file_info["status"] != "uploaded":
                continue
            
            filename = file_info["filename"]
            dest_path = Path(file_info["dest_path"])
            expected_checksum = file_info.get("checksum_dest")
            
            if not dest_path.exists():
                logger.error(f"✗ File not found: {dest_path}")
                results[filename] = False
                continue
            
            if expected_checksum:
                logger.info(f"Verifying {filename}")
                actual_checksum = self.calculate_checksum(dest_path)
                
                if actual_checksum == expected_checksum:
                    logger.info(f"✓ {filename} integrity verified")
                    results[filename] = True
                else:
                    logger.error(f"✗ Checksum mismatch for {filename}")
                    logger.error(f"  Expected: {expected_checksum}")
                    logger.error(f"  Actual:   {actual_checksum}")
                    results[filename] = False
            else:
                logger.warning(f"No checksum available for {filename}, skipping verification")
        
        successful = sum(1 for v in results.values() if v)
        failed = len(results) - successful
        
        logger.info(f"Verification complete: {successful} passed, {failed} failed")
        
        return results
    
    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format byte size as human-readable string"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    @staticmethod
    def _format_rate(size_bytes: int, time_seconds: float) -> str:
        """Format transfer rate as human-readable string"""
        if time_seconds == 0:
            return "N/A"
        rate_bps = size_bytes / time_seconds
        for unit in ['B/s', 'KB/s', 'MB/s', 'GB/s']:
            if rate_bps < 1024.0:
                return f"{rate_bps:.2f} {unit}"
            rate_bps /= 1024.0
        return f"{rate_bps:.2f} TB/s"


def main():
    """Command-line interface for the FSx uploader"""
    parser = argparse.ArgumentParser(
        description="Upload hg38 chromosome data to FSx NetApp ONTAP volume"
    )
    parser.add_argument(
        "--source-dir",
        type=str,
        required=True,
        help="Directory containing files to upload"
    )
    parser.add_argument(
        "--fsx-mount",
        type=str,
        required=True,
        help="FSx volume mount point (e.g., /mnt/fsx)"
    )
    parser.add_argument(
        "--dest-subdir",
        type=str,
        help="Optional subdirectory within FSx mount point"
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="*.fa.gz",
        help="Glob pattern for files to upload (default: *.fa.gz)"
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
        "--no-verify",
        action="store_true",
        help="Disable checksum verification"
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Disable resume (re-upload all files)"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify uploaded files against manifest"
    )
    parser.add_argument(
        "--manifest",
        type=str,
        help="Path to manifest file (default: fsx-mount/upload_manifest.json)"
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize uploader
        uploader = FSxUploader(
            source_dir=args.source_dir,
            fsx_mount_point=args.fsx_mount,
            max_retries=args.max_retries,
            retry_delay=args.retry_delay,
            verify_checksums=not args.no_verify,
            resume=not args.no_resume
        )
        
        # Verify mount access
        if not uploader.verify_mount_access():
            logger.error("FSx mount is not accessible. Please check mount status.")
            sys.exit(1)
        
        if args.verify_only:
            # Verify uploaded files
            results = uploader.verify_uploaded_files(manifest_path=args.manifest)
            failed = sum(1 for v in results.values() if not v)
            sys.exit(0 if failed == 0 else 1)
        else:
            # Upload files
            upload_result = uploader.upload_directory(
                pattern=args.pattern,
                dest_subdir=args.dest_subdir
            )
            
            # Save manifest
            uploader.save_upload_manifest(upload_result, manifest_path=args.manifest)
            
            # Check for failures
            if upload_result["failed_files"] > 0:
                logger.error(f"{upload_result['failed_files']} files failed to upload")
                sys.exit(1)
            else:
                logger.info("All files uploaded successfully")
                sys.exit(0)
                
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
