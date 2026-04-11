#!/usr/bin/env python3
"""
Data Integrity Validator for FSx Upload Verification

Validates data integrity before and after FSx upload by comparing checksums
and file sizes between source files and FSx destination files. Integrates with
checksum_calculator and fsx_uploader modules to provide comprehensive validation.

This module is part of Phase 2: Data Preparation for cross-AZ FSx validation.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Import existing modules
from checksum_calculator import ChecksumCalculator
from fsx_uploader import FSxUploader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass


class DataIntegrityValidator:
    """Validates data integrity before and after FSx upload"""
    
    def __init__(
        self,
        source_dir: str,
        fsx_mount_path: str,
        checksum_manifest_path: Optional[str] = None
    ):
        """
        Initialize the data integrity validator
        
        Args:
            source_dir: Directory containing source files
            fsx_mount_path: Mount point of FSx volume
            checksum_manifest_path: Path to checksum manifest (optional)
        """
        self.source_dir = Path(source_dir)
        self.fsx_mount_path = Path(fsx_mount_path)
        
        # Validate directories exist
        if not self.source_dir.exists():
            raise ValueError(f"Source directory does not exist: {source_dir}")
        
        if not self.fsx_mount_path.exists():
            raise ValueError(f"FSx mount path does not exist: {fsx_mount_path}")
        
        # Initialize checksum calculator
        self.checksum_calculator = ChecksumCalculator(
            data_dir=str(self.source_dir),
            manifest_path=checksum_manifest_path
        )
        
        logger.info(f"Initialized DataIntegrityValidator")
        logger.info(f"  Source: {source_dir}")
        logger.info(f"  FSx mount: {fsx_mount_path}")
    
    def verify_file_integrity(
        self,
        source_file: Path,
        dest_file: Path
    ) -> Dict[str, any]:
        """
        Verify integrity of a single file by comparing source and destination
        
        Args:
            source_file: Path to source file
            dest_file: Path to destination file on FSx
            
        Returns:
            Dictionary with verification results:
                - filename: Name of the file
                - source_path: Source file path
                - dest_path: Destination file path
                - size_match: Whether file sizes match
                - source_size: Source file size in bytes
                - dest_size: Destination file size in bytes
                - checksum_match: Whether checksums match
                - source_md5: Source file MD5 checksum
                - dest_md5: Destination file MD5 checksum
                - source_sha256: Source file SHA256 checksum
                - dest_sha256: Destination file SHA256 checksum
                - valid: Overall validation result
                - error_message: Error message if validation failed
        """
        filename = source_file.name
        logger.info(f"Verifying integrity of {filename}")
        
        result = {
            "filename": filename,
            "source_path": str(source_file),
            "dest_path": str(dest_file),
            "valid": False
        }
        
        try:
            # Check if destination file exists
            if not dest_file.exists():
                result["error_message"] = "Destination file does not exist"
                logger.error(f"✗ {filename}: Destination file not found")
                return result
            
            # Verify file sizes
            source_size = source_file.stat().st_size
            dest_size = dest_file.stat().st_size
            size_match = source_size == dest_size
            
            result["source_size"] = source_size
            result["dest_size"] = dest_size
            result["size_match"] = size_match
            
            if not size_match:
                result["error_message"] = (
                    f"File size mismatch: source={source_size}, dest={dest_size}"
                )
                logger.error(f"✗ {filename}: Size mismatch")
                logger.error(f"  Source: {self._format_size(source_size)}")
                logger.error(f"  Dest:   {self._format_size(dest_size)}")
                return result
            
            # Calculate and compare checksums
            logger.info(f"Calculating checksums for {filename}")
            
            source_checksums = self.checksum_calculator.calculate_file_checksums(source_file)
            
            # Calculate destination checksums using same method
            dest_md5 = self._calculate_checksum(dest_file, 'md5')
            dest_sha256 = self._calculate_checksum(dest_file, 'sha256')
            
            result["source_md5"] = source_checksums['md5']
            result["dest_md5"] = dest_md5
            result["source_sha256"] = source_checksums['sha256']
            result["dest_sha256"] = dest_sha256
            
            md5_match = source_checksums['md5'] == dest_md5
            sha256_match = source_checksums['sha256'] == dest_sha256
            
            result["checksum_match"] = md5_match and sha256_match
            
            if not md5_match or not sha256_match:
                errors = []
                if not md5_match:
                    errors.append("MD5 mismatch")
                    logger.error(f"✗ {filename}: MD5 mismatch")
                    logger.error(f"  Source: {source_checksums['md5']}")
                    logger.error(f"  Dest:   {dest_md5}")
                
                if not sha256_match:
                    errors.append("SHA256 mismatch")
                    logger.error(f"✗ {filename}: SHA256 mismatch")
                    logger.error(f"  Source: {source_checksums['sha256']}")
                    logger.error(f"  Dest:   {dest_sha256}")
                
                result["error_message"] = ", ".join(errors)
                return result
            
            # All checks passed
            result["valid"] = True
            logger.info(f"✓ {filename}: Integrity verified")
            
        except Exception as e:
            result["error_message"] = str(e)
            logger.error(f"✗ {filename}: Validation error: {e}")
        
        return result
    
    def validate_upload(
        self,
        dest_subdir: Optional[str] = None,
        pattern: str = "*.fa.gz"
    ) -> Dict[str, any]:
        """
        Validate upload integrity for all files matching pattern
        
        Args:
            dest_subdir: Optional subdirectory within FSx mount point
            pattern: Glob pattern for files to validate (default: *.fa.gz)
            
        Returns:
            Dictionary with validation summary:
                - files: List of individual file validation results
                - total_files: Total number of files validated
                - valid_files: Number of files that passed validation
                - invalid_files: Number of files that failed validation
                - total_size_bytes: Total size of validated data
                - validation_timestamp: When validation was performed
        """
        # Find source files
        source_files = list(self.source_dir.glob(pattern))
        
        if not source_files:
            logger.warning(f"No files matching pattern '{pattern}' found in {self.source_dir}")
            return {
                "files": [],
                "total_files": 0,
                "valid_files": 0,
                "invalid_files": 0,
                "total_size_bytes": 0,
                "validation_timestamp": datetime.utcnow().isoformat() + 'Z'
            }
        
        logger.info(f"Found {len(source_files)} files to validate")
        
        # Determine destination directory
        if dest_subdir:
            dest_dir = self.fsx_mount_path / dest_subdir
        else:
            dest_dir = self.fsx_mount_path
        
        if not dest_dir.exists():
            raise ValidationError(f"Destination directory does not exist: {dest_dir}")
        
        # Validate each file
        results = []
        valid_count = 0
        invalid_count = 0
        total_size = 0
        
        for i, source_file in enumerate(sorted(source_files), 1):
            logger.info(f"Validating file {i}/{len(source_files)}: {source_file.name}")
            
            dest_file = dest_dir / source_file.name
            result = self.verify_file_integrity(source_file, dest_file)
            results.append(result)
            
            if result["valid"]:
                valid_count += 1
                total_size += result["source_size"]
            else:
                invalid_count += 1
        
        # Summary
        logger.info(f"Validation complete:")
        logger.info(f"  - Total files: {len(source_files)}")
        logger.info(f"  - Valid: {valid_count}")
        logger.info(f"  - Invalid: {invalid_count}")
        logger.info(f"  - Total size: {self._format_size(total_size)}")
        
        return {
            "files": results,
            "total_files": len(source_files),
            "valid_files": valid_count,
            "invalid_files": invalid_count,
            "total_size_bytes": total_size,
            "validation_timestamp": datetime.utcnow().isoformat() + 'Z',
            "dest_subdir": dest_subdir
        }
    
    def generate_validation_report(
        self,
        validation_results: Dict[str, any],
        report_path: Optional[str] = None
    ) -> Path:
        """
        Generate validation report and save to file
        
        Args:
            validation_results: Results from validate_upload
            report_path: Path to save report (default: source_dir/validation_report.json)
            
        Returns:
            Path to saved report file
        """
        if report_path:
            report_file = Path(report_path)
        else:
            report_file = self.source_dir / "validation_report.json"
        
        # Build comprehensive report
        report = {
            "validation_summary": {
                "total_files": validation_results["total_files"],
                "valid_files": validation_results["valid_files"],
                "invalid_files": validation_results["invalid_files"],
                "success_rate": (
                    validation_results["valid_files"] / validation_results["total_files"] * 100
                    if validation_results["total_files"] > 0 else 0
                ),
                "total_size_bytes": validation_results["total_size_bytes"],
                "total_size_human": self._format_size(validation_results["total_size_bytes"]),
                "validation_timestamp": validation_results["validation_timestamp"]
            },
            "configuration": {
                "source_dir": str(self.source_dir),
                "fsx_mount_path": str(self.fsx_mount_path),
                "dest_subdir": validation_results.get("dest_subdir")
            },
            "file_results": validation_results["files"],
            "failed_files": [
                {
                    "filename": f["filename"],
                    "error": f.get("error_message", "Unknown error")
                }
                for f in validation_results["files"]
                if not f["valid"]
            ]
        }
        
        logger.info(f"Saving validation report to {report_file}")
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info("Validation report saved successfully")
        
        # Also generate human-readable summary
        self._generate_text_summary(report, report_file.with_suffix('.txt'))
        
        return report_file
    
    def _generate_text_summary(self, report: Dict[str, any], output_path: Path) -> None:
        """Generate human-readable text summary of validation report"""
        summary = report["validation_summary"]
        config = report["configuration"]
        
        lines = [
            "=" * 80,
            "DATA INTEGRITY VALIDATION REPORT",
            "=" * 80,
            "",
            f"Validation Timestamp: {summary['validation_timestamp']}",
            "",
            "Configuration:",
            f"  Source Directory: {config['source_dir']}",
            f"  FSx Mount Path:   {config['fsx_mount_path']}",
            f"  Destination Subdir: {config.get('dest_subdir', 'N/A')}",
            "",
            "Summary:",
            f"  Total Files:    {summary['total_files']}",
            f"  Valid Files:    {summary['valid_files']}",
            f"  Invalid Files:  {summary['invalid_files']}",
            f"  Success Rate:   {summary['success_rate']:.2f}%",
            f"  Total Size:     {summary['total_size_human']}",
            "",
        ]
        
        if report["failed_files"]:
            lines.extend([
                "Failed Files:",
                "-" * 80,
            ])
            for failed in report["failed_files"]:
                lines.append(f"  {failed['filename']}: {failed['error']}")
            lines.append("")
        
        lines.extend([
            "=" * 80,
            f"Validation {'PASSED' if summary['invalid_files'] == 0 else 'FAILED'}",
            "=" * 80,
        ])
        
        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))
        
        logger.info(f"Text summary saved to {output_path}")
    
    def _calculate_checksum(self, filepath: Path, algorithm: str) -> str:
        """Calculate checksum for a file using specified algorithm"""
        import hashlib
        
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
    
    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format byte size as human-readable string"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"


def main():
    """Command-line interface for the data integrity validator"""
    parser = argparse.ArgumentParser(
        description="Validate data integrity before and after FSx upload"
    )
    parser.add_argument(
        "--source-dir",
        type=str,
        required=True,
        help="Directory containing source files"
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
        help="Glob pattern for files to validate (default: *.fa.gz)"
    )
    parser.add_argument(
        "--manifest",
        type=str,
        help="Path to checksum manifest file (optional)"
    )
    parser.add_argument(
        "--report",
        type=str,
        help="Path to save validation report (default: source-dir/validation_report.json)"
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize validator
        validator = DataIntegrityValidator(
            source_dir=args.source_dir,
            fsx_mount_path=args.fsx_mount,
            checksum_manifest_path=args.manifest
        )
        
        # Validate upload
        validation_results = validator.validate_upload(
            dest_subdir=args.dest_subdir,
            pattern=args.pattern
        )
        
        # Generate report
        report_path = validator.generate_validation_report(
            validation_results,
            report_path=args.report
        )
        
        logger.info(f"Validation report saved to {report_path}")
        
        # Exit with appropriate code
        if validation_results["invalid_files"] > 0:
            logger.error(f"Validation failed: {validation_results['invalid_files']} files invalid")
            sys.exit(1)
        else:
            logger.info("All files validated successfully")
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
