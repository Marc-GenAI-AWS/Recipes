#!/usr/bin/env python3
"""
Checksum Calculator for Downloaded Chromosome Files

Calculates MD5 and SHA256 checksums for downloaded hg38 chromosome files
and stores them in a manifest file for data integrity validation.

This module enhances the hg38_downloader by providing additional checksum
types and manifest generation capabilities.
"""

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ChecksumCalculator:
    """Calculates checksums for chromosome files and manages manifest"""
    
    def __init__(self, data_dir: str, manifest_path: Optional[str] = None):
        """
        Initialize the checksum calculator
        
        Args:
            data_dir: Directory containing chromosome files
            manifest_path: Path to manifest file (default: data_dir/checksums_manifest.json)
        """
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
            raise ValueError(f"Data directory does not exist: {data_dir}")
        
        if manifest_path:
            self.manifest_path = Path(manifest_path)
        else:
            self.manifest_path = self.data_dir / "checksums_manifest.json"
        
        logger.info(f"Initialized ChecksumCalculator with data_dir={data_dir}")
        logger.info(f"Manifest path: {self.manifest_path}")
    
    def calculate_file_checksums(self, filepath: Path) -> Dict[str, str]:
        """
        Calculate MD5 and SHA256 checksums for a file
        
        Args:
            filepath: Path to the file
            
        Returns:
            Dictionary with 'md5' and 'sha256' checksums as hex strings
        """
        md5_hash = hashlib.md5()
        sha256_hash = hashlib.sha256()
        
        logger.info(f"Calculating checksums for {filepath.name}")
        
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                md5_hash.update(chunk)
                sha256_hash.update(chunk)
        
        checksums = {
            'md5': md5_hash.hexdigest(),
            'sha256': sha256_hash.hexdigest()
        }
        
        logger.info(f"MD5: {checksums['md5']}")
        logger.info(f"SHA256: {checksums['sha256']}")
        
        return checksums

    def calculate_directory_checksums(
        self,
        pattern: str = "*.fa.gz"
    ) -> Dict[str, Dict[str, any]]:
        """
        Calculate checksums for all matching files in the data directory
        
        Args:
            pattern: Glob pattern for files to process (default: *.fa.gz)
            
        Returns:
            Dictionary mapping filename to file metadata including checksums
        """
        files = list(self.data_dir.glob(pattern))
        
        if not files:
            logger.warning(f"No files matching pattern '{pattern}' found in {self.data_dir}")
            return {}
        
        logger.info(f"Found {len(files)} files matching pattern '{pattern}'")
        
        results = {}
        for filepath in sorted(files):
            try:
                checksums = self.calculate_file_checksums(filepath)
                file_size = filepath.stat().st_size
                
                results[filepath.name] = {
                    'filename': filepath.name,
                    'filepath': str(filepath.absolute()),
                    'size_bytes': file_size,
                    'size_human': self._format_size(file_size),
                    'md5': checksums['md5'],
                    'sha256': checksums['sha256'],
                    'calculated_at': datetime.utcnow().isoformat() + 'Z'
                }
                
            except Exception as e:
                logger.error(f"Failed to calculate checksums for {filepath.name}: {e}")
                results[filepath.name] = {
                    'filename': filepath.name,
                    'error': str(e)
                }
        
        return results
    
    def generate_manifest(
        self,
        pattern: str = "*.fa.gz",
        include_metadata: bool = True
    ) -> Dict[str, any]:
        """
        Generate a manifest file with checksums for all matching files
        
        Args:
            pattern: Glob pattern for files to include (default: *.fa.gz)
            include_metadata: Include manifest metadata (timestamp, file count, etc.)
            
        Returns:
            Manifest dictionary
        """
        logger.info("Generating checksum manifest")
        
        file_checksums = self.calculate_directory_checksums(pattern)
        
        manifest = {
            'files': file_checksums
        }
        
        if include_metadata:
            successful_files = [f for f in file_checksums.values() if 'error' not in f]
            failed_files = [f for f in file_checksums.values() if 'error' in f]
            total_size = sum(f.get('size_bytes', 0) for f in successful_files)
            
            manifest['metadata'] = {
                'generated_at': datetime.utcnow().isoformat() + 'Z',
                'data_directory': str(self.data_dir.absolute()),
                'file_pattern': pattern,
                'total_files': len(file_checksums),
                'successful_files': len(successful_files),
                'failed_files': len(failed_files),
                'total_size_bytes': total_size,
                'total_size_human': self._format_size(total_size)
            }
        
        return manifest
    
    def save_manifest(
        self,
        manifest: Optional[Dict[str, any]] = None,
        pattern: str = "*.fa.gz"
    ) -> Path:
        """
        Save manifest to file
        
        Args:
            manifest: Pre-generated manifest (if None, generates new one)
            pattern: Glob pattern for files to include (used if manifest is None)
            
        Returns:
            Path to saved manifest file
        """
        if manifest is None:
            manifest = self.generate_manifest(pattern)
        
        logger.info(f"Saving manifest to {self.manifest_path}")
        
        with open(self.manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        logger.info(f"Manifest saved successfully")
        
        return self.manifest_path
    
    def load_manifest(self) -> Dict[str, any]:
        """
        Load manifest from file
        
        Returns:
            Manifest dictionary
            
        Raises:
            FileNotFoundError: If manifest file doesn't exist
        """
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {self.manifest_path}")
        
        logger.info(f"Loading manifest from {self.manifest_path}")
        
        with open(self.manifest_path, 'r') as f:
            manifest = json.load(f)
        
        return manifest
    
    def verify_file_integrity(
        self,
        filename: str,
        manifest: Optional[Dict[str, any]] = None
    ) -> bool:
        """
        Verify a file's integrity against the manifest
        
        Args:
            filename: Name of the file to verify
            manifest: Manifest to verify against (if None, loads from file)
            
        Returns:
            True if file matches manifest checksums, False otherwise
        """
        if manifest is None:
            manifest = self.load_manifest()
        
        if filename not in manifest['files']:
            logger.error(f"File {filename} not found in manifest")
            return False
        
        expected = manifest['files'][filename]
        if 'error' in expected:
            logger.error(f"File {filename} has error in manifest: {expected['error']}")
            return False
        
        filepath = self.data_dir / filename
        if not filepath.exists():
            logger.error(f"File not found: {filepath}")
            return False
        
        logger.info(f"Verifying integrity of {filename}")
        
        actual_checksums = self.calculate_file_checksums(filepath)
        
        md5_match = actual_checksums['md5'] == expected['md5']
        sha256_match = actual_checksums['sha256'] == expected['sha256']
        
        if md5_match and sha256_match:
            logger.info(f"✓ {filename} integrity verified")
            return True
        else:
            if not md5_match:
                logger.error(f"✗ MD5 mismatch for {filename}")
                logger.error(f"  Expected: {expected['md5']}")
                logger.error(f"  Actual:   {actual_checksums['md5']}")
            if not sha256_match:
                logger.error(f"✗ SHA256 mismatch for {filename}")
                logger.error(f"  Expected: {expected['sha256']}")
                logger.error(f"  Actual:   {actual_checksums['sha256']}")
            return False
    
    def verify_all_files(
        self,
        manifest: Optional[Dict[str, any]] = None
    ) -> Dict[str, bool]:
        """
        Verify integrity of all files in the manifest
        
        Args:
            manifest: Manifest to verify against (if None, loads from file)
            
        Returns:
            Dictionary mapping filename to verification result (True/False)
        """
        if manifest is None:
            manifest = self.load_manifest()
        
        results = {}
        for filename in manifest['files'].keys():
            if 'error' not in manifest['files'][filename]:
                results[filename] = self.verify_file_integrity(filename, manifest)
        
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


def main():
    """Command-line interface for the checksum calculator"""
    parser = argparse.ArgumentParser(
        description="Calculate checksums for hg38 chromosome files and manage manifest"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        required=True,
        help="Directory containing chromosome files"
    )
    parser.add_argument(
        "--manifest",
        type=str,
        help="Path to manifest file (default: data-dir/checksums_manifest.json)"
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="*.fa.gz",
        help="Glob pattern for files to process (default: *.fa.gz)"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Generate command
    generate_parser = subparsers.add_parser('generate', help='Generate checksum manifest')
    
    # Verify command
    verify_parser = subparsers.add_parser('verify', help='Verify file integrity')
    verify_parser.add_argument(
        '--file',
        type=str,
        help='Specific file to verify (if not specified, verifies all files)'
    )
    
    # Calculate command
    calculate_parser = subparsers.add_parser('calculate', help='Calculate checksums for a file')
    calculate_parser.add_argument(
        'file',
        type=str,
        help='File to calculate checksums for'
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        calculator = ChecksumCalculator(
            data_dir=args.data_dir,
            manifest_path=args.manifest
        )
        
        if args.command == 'generate':
            manifest = calculator.generate_manifest(pattern=args.pattern)
            calculator.save_manifest(manifest)
            
            metadata = manifest.get('metadata', {})
            logger.info(f"Generated manifest with {metadata.get('successful_files', 0)} files")
            logger.info(f"Total size: {metadata.get('total_size_human', 'unknown')}")
            
        elif args.command == 'verify':
            if args.file:
                result = calculator.verify_file_integrity(args.file)
                sys.exit(0 if result else 1)
            else:
                results = calculator.verify_all_files()
                failed = sum(1 for v in results.values() if not v)
                sys.exit(0 if failed == 0 else 1)
        
        elif args.command == 'calculate':
            filepath = Path(args.data_dir) / args.file
            if not filepath.exists():
                logger.error(f"File not found: {filepath}")
                sys.exit(1)
            
            checksums = calculator.calculate_file_checksums(filepath)
            print(f"\nChecksums for {args.file}:")
            print(f"MD5:    {checksums['md5']}")
            print(f"SHA256: {checksums['sha256']}")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
