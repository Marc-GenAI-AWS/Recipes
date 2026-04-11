#!/usr/bin/env python3
"""
Prepare 10GB Dataset (chr1, chr2) - Task 2.5

This script orchestrates the complete workflow for preparing the 10GB validation dataset:
1. Get FSx SVM DNS name from AWS
2. Create local directory structure
3. Download chr1 and chr2 from UCSC
4. Calculate checksums
5. Mount FSx volume (if not already mounted)
6. Upload to FSx with dest_subdir="phase_10gb"
7. Validate upload integrity
8. Generate validation report

Usage:
    python prepare_10gb_dataset.py --region us-west-2 --fsx-svm-id svm-04e40592311d0bdfb
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

# Import our existing modules
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


class FSxSVMManager:
    """Manages FSx SVM operations including DNS name retrieval"""
    
    def __init__(self, region: str = 'us-west-2'):
        """Initialize FSx SVM Manager"""
        self.region = region
        
    def get_svm_dns_name(self, svm_id: str) -> str:
        """
        Get FSx SVM DNS name using AWS CLI
        
        Args:
            svm_id: FSx SVM ID (e.g., svm-04e40592311d0bdfb)
            
        Returns:
            SVM DNS name
            
        Raises:
            RuntimeError: If AWS CLI command fails
        """
        logger.info(f"Retrieving DNS name for SVM {svm_id}")
        
        try:
            # Use AWS CLI to describe storage virtual machine
            cmd = [
                'aws', 'fsx', 'describe-storage-virtual-machines',
                '--storage-virtual-machine-ids', svm_id,
                '--region', self.region,
                '--output', 'json'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse JSON response
            response = json.loads(result.stdout)
            
            if not response.get('StorageVirtualMachines'):
                raise RuntimeError(f"SVM {svm_id} not found")
            
            svm = response['StorageVirtualMachines'][0]
            
            # Get NFS DNS name
            endpoints = svm.get('Endpoints', {})
            nfs_endpoint = endpoints.get('Nfs', {})
            dns_name = nfs_endpoint.get('DNSName')
            
            if not dns_name:
                raise RuntimeError(f"NFS DNS name not found for SVM {svm_id}")
            
            logger.info(f"SVM DNS name: {dns_name}")
            return dns_name
            
        except subprocess.CalledProcessError as e:
            logger.error(f"AWS CLI command failed: {e.stderr}")
            raise RuntimeError(f"Failed to get SVM DNS name: {e.stderr}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AWS CLI response: {e}")
            raise RuntimeError(f"Failed to parse AWS CLI response: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise


class FSxMountHelper:
    """Helper for mounting FSx volumes"""
    
    @staticmethod
    def is_mounted(mount_point: str) -> bool:
        """
        Check if FSx volume is already mounted
        
        Args:
            mount_point: Mount point path
            
        Returns:
            True if mounted, False otherwise
        """
        mount_point_path = Path(mount_point)
        
        if not mount_point_path.exists():
            return False
        
        try:
            # Check if it's a mount point
            result = subprocess.run(
                ['mountpoint', '-q', mount_point],
                capture_output=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            # mountpoint command not available, check /proc/mounts
            try:
                with open('/proc/mounts', 'r') as f:
                    mounts = f.read()
                    return mount_point in mounts
            except:
                # Fallback: assume not mounted if we can't check
                return False
    
    @staticmethod
    def mount_fsx(
        svm_dns_name: str,
        volume_name: str,
        mount_point: str,
        force: bool = False
    ) -> bool:
        """
        Mount FSx volume using NFS
        
        Args:
            svm_dns_name: SVM DNS name
            volume_name: Volume name (e.g., genomics_training_data)
            mount_point: Local mount point (e.g., /mnt/fsx)
            force: Force remount if already mounted
            
        Returns:
            True if mounted successfully
            
        Raises:
            RuntimeError: If mount fails
        """
        mount_point_path = Path(mount_point)
        
        # Check if already mounted
        if FSxMountHelper.is_mounted(mount_point):
            if not force:
                logger.info(f"{mount_point} is already mounted")
                return True
            else:
                logger.info(f"Unmounting {mount_point}")
                subprocess.run(['sudo', 'umount', mount_point], check=True)
        
        # Create mount point if it doesn't exist
        if not mount_point_path.exists():
            logger.info(f"Creating mount point: {mount_point}")
            mount_point_path.mkdir(parents=True, exist_ok=True)
        
        # Mount FSx volume
        nfs_path = f"{svm_dns_name}:/{volume_name}"
        logger.info(f"Mounting {nfs_path} to {mount_point}")
        
        try:
            cmd = [
                'sudo', 'mount', '-t', 'nfs',
                '-o', 'nfsvers=3,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2',
                nfs_path,
                mount_point
            ]
            
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"Successfully mounted {nfs_path} to {mount_point}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Mount failed: {e.stderr}")
            raise RuntimeError(f"Failed to mount FSx volume: {e.stderr}")


def prepare_10gb_dataset(
    region: str,
    fsx_svm_id: str,
    fsx_volume_name: str,
    fsx_mount_point: str,
    local_data_dir: str,
    skip_download: bool = False,
    skip_upload: bool = False,
    skip_mount: bool = False
) -> Dict[str, any]:
    """
    Prepare 10GB dataset (chr1, chr2) with complete workflow
    
    Args:
        region: AWS region
        fsx_svm_id: FSx SVM ID
        fsx_volume_name: FSx volume name
        fsx_mount_point: Local mount point for FSx
        local_data_dir: Local directory for downloaded data
        skip_download: Skip download if files already exist
        skip_upload: Skip upload step
        skip_mount: Skip mount step (assume already mounted)
        
    Returns:
        Dictionary with workflow results
    """
    results = {
        "phase": "10GB",
        "chromosomes": ["chr1", "chr2"],
        "local_data_dir": local_data_dir,
        "fsx_mount_point": fsx_mount_point,
        "steps": {}
    }
    
    # Step 1: Get FSx SVM DNS name
    logger.info("=" * 80)
    logger.info("STEP 1: Get FSx SVM DNS name")
    logger.info("=" * 80)
    
    svm_manager = FSxSVMManager(region=region)
    svm_dns_name = svm_manager.get_svm_dns_name(fsx_svm_id)
    results["svm_dns_name"] = svm_dns_name
    results["steps"]["get_svm_dns"] = {"status": "success", "dns_name": svm_dns_name}
    
    # Step 2: Create local directory
    logger.info("=" * 80)
    logger.info("STEP 2: Create local directory structure")
    logger.info("=" * 80)
    
    local_dir = Path(local_data_dir)
    local_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Local data directory: {local_dir}")
    results["steps"]["create_local_dir"] = {"status": "success", "path": str(local_dir)}
    
    # Step 3: Download chr1 and chr2
    logger.info("=" * 80)
    logger.info("STEP 3: Download chr1 and chr2 from UCSC")
    logger.info("=" * 80)
    
    if skip_download and (local_dir / "chr1.fa.gz").exists() and (local_dir / "chr2.fa.gz").exists():
        logger.info("Skipping download (files already exist)")
        results["steps"]["download"] = {"status": "skipped"}
    else:
        downloader = HG38Downloader(
            output_dir=str(local_dir),
            max_retries=3,
            retry_delay=5,
            timeout=600
        )
        
        download_results = downloader.download_chromosomes(
            chromosomes=["chr1", "chr2"],
            force=not skip_download
        )
        
        results["steps"]["download"] = {
            "status": "success",
            "files": download_results
        }
        
        # Check for failures
        failed = [r for r in download_results if r.get("status") == "failed"]
        if failed:
            raise RuntimeError(f"Failed to download {len(failed)} files")
    
    # Step 4: Calculate checksums
    logger.info("=" * 80)
    logger.info("STEP 4: Calculate checksums")
    logger.info("=" * 80)
    
    checksum_manifest_path = local_dir / "checksums_manifest.json"
    calculator = ChecksumCalculator(
        data_dir=str(local_dir),
        manifest_path=str(checksum_manifest_path)
    )
    
    manifest = calculator.generate_manifest(pattern="*.fa.gz")
    calculator.save_manifest(manifest)
    
    results["steps"]["checksums"] = {
        "status": "success",
        "manifest_path": str(checksum_manifest_path),
        "files": len(manifest.get("files", {}))
    }
    
    # Step 5: Mount FSx volume
    if not skip_mount:
        logger.info("=" * 80)
        logger.info("STEP 5: Mount FSx volume")
        logger.info("=" * 80)
        
        mount_helper = FSxMountHelper()
        mount_helper.mount_fsx(
            svm_dns_name=svm_dns_name,
            volume_name=fsx_volume_name,
            mount_point=fsx_mount_point,
            force=False
        )
        
        results["steps"]["mount"] = {
            "status": "success",
            "mount_point": fsx_mount_point
        }
    else:
        logger.info("Skipping mount step (assume already mounted)")
        results["steps"]["mount"] = {"status": "skipped"}
    
    # Step 6: Upload to FSx
    if not skip_upload:
        logger.info("=" * 80)
        logger.info("STEP 6: Upload to FSx")
        logger.info("=" * 80)
        
        uploader = FSxUploader(
            source_dir=str(local_dir),
            fsx_mount_point=fsx_mount_point,
            max_retries=3,
            retry_delay=5,
            verify_checksums=True,
            resume=True
        )
        
        # Verify mount access
        if not uploader.verify_mount_access():
            raise RuntimeError("FSx mount is not accessible")
        
        # Upload files
        upload_result = uploader.upload_directory(
            pattern="*.fa.gz",
            dest_subdir="phase_10gb"
        )
        
        # Save upload manifest
        upload_manifest_path = local_dir / "upload_manifest.json"
        uploader.save_upload_manifest(upload_result, manifest_path=str(upload_manifest_path))
        
        results["steps"]["upload"] = {
            "status": "success",
            "manifest_path": str(upload_manifest_path),
            "summary": upload_result
        }
        
        # Check for failures
        if upload_result["failed_files"] > 0:
            raise RuntimeError(f"Failed to upload {upload_result['failed_files']} files")
    else:
        logger.info("Skipping upload step")
        results["steps"]["upload"] = {"status": "skipped"}
    
    # Step 7: Validate upload integrity
    if not skip_upload:
        logger.info("=" * 80)
        logger.info("STEP 7: Validate upload integrity")
        logger.info("=" * 80)
        
        validator = DataIntegrityValidator(
            source_dir=str(local_dir),
            fsx_mount_path=fsx_mount_point,
            checksum_manifest_path=str(checksum_manifest_path)
        )
        
        validation_results = validator.validate_upload(
            dest_subdir="phase_10gb",
            pattern="*.fa.gz"
        )
        
        # Generate validation report
        validation_report_path = validator.generate_validation_report(
            validation_results,
            report_path=str(local_dir / "validation_report.json")
        )
        
        results["steps"]["validation"] = {
            "status": "success",
            "report_path": str(validation_report_path),
            "summary": {
                "total_files": validation_results["total_files"],
                "valid_files": validation_results["valid_files"],
                "invalid_files": validation_results["invalid_files"]
            }
        }
        
        # Check for validation failures
        if validation_results["invalid_files"] > 0:
            raise RuntimeError(f"Validation failed: {validation_results['invalid_files']} files invalid")
    else:
        logger.info("Skipping validation step")
        results["steps"]["validation"] = {"status": "skipped"}
    
    # Step 8: Generate summary
    logger.info("=" * 80)
    logger.info("WORKFLOW COMPLETE")
    logger.info("=" * 80)
    
    return results


def main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(
        description="Prepare 10GB dataset (chr1, chr2) for cross-AZ FSx validation"
    )
    parser.add_argument(
        "--region",
        type=str,
        default="us-west-2",
        help="AWS region (default: us-west-2)"
    )
    parser.add_argument(
        "--fsx-svm-id",
        type=str,
        default="svm-04e40592311d0bdfb",
        help="FSx SVM ID (default: svm-04e40592311d0bdfb)"
    )
    parser.add_argument(
        "--fsx-volume-name",
        type=str,
        default="genomics_training_data",
        help="FSx volume name (default: genomics_training_data)"
    )
    parser.add_argument(
        "--fsx-mount-point",
        type=str,
        default="/mnt/fsx",
        help="FSx mount point (default: /mnt/fsx)"
    )
    parser.add_argument(
        "--local-data-dir",
        type=str,
        default="./validation_datasets/10gb",
        help="Local directory for downloaded data (default: ./validation_datasets/10gb)"
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip download if files already exist"
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Skip upload step"
    )
    parser.add_argument(
        "--skip-mount",
        action="store_true",
        help="Skip mount step (assume already mounted)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Path to save workflow results JSON (optional)"
    )
    
    args = parser.parse_args()
    
    try:
        # Execute workflow
        results = prepare_10gb_dataset(
            region=args.region,
            fsx_svm_id=args.fsx_svm_id,
            fsx_volume_name=args.fsx_volume_name,
            fsx_mount_point=args.fsx_mount_point,
            local_data_dir=args.local_data_dir,
            skip_download=args.skip_download,
            skip_upload=args.skip_upload,
            skip_mount=args.skip_mount
        )
        
        # Save results if output path specified
        if args.output:
            output_path = Path(args.output)
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2)
            logger.info(f"Workflow results saved to {output_path}")
        
        # Print summary
        logger.info("")
        logger.info("=" * 80)
        logger.info("SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Phase: {results['phase']}")
        logger.info(f"Chromosomes: {', '.join(results['chromosomes'])}")
        logger.info(f"Local data directory: {results['local_data_dir']}")
        logger.info(f"FSx mount point: {results['fsx_mount_point']}")
        logger.info(f"SVM DNS name: {results['svm_dns_name']}")
        logger.info("")
        logger.info("Steps completed:")
        for step_name, step_result in results["steps"].items():
            status = step_result.get("status", "unknown")
            logger.info(f"  - {step_name}: {status}")
        logger.info("")
        logger.info("All steps completed successfully!")
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
