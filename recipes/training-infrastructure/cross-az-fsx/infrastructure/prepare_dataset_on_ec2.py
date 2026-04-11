#!/usr/bin/env python3
"""
High-Level Orchestration Script for EC2-Based Data Preparation

Orchestrates the complete workflow:
1. Launch EC2 instance in same AZ as FSx
2. Monitor data preparation progress
3. Handle errors and cleanup
4. Terminate instance when complete

This script provides a simple CLI interface for preparing datasets at any scale.
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import boto3
from botocore.exceptions import ClientError

from ec2_data_prep_manager import EC2DataPrepManager, EC2DataPrepError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatasetPreparationOrchestrator:
    """Orchestrates EC2-based dataset preparation workflow"""
    
    def __init__(
        self,
        region: str = "us-west-2",
        availability_zone: str = "us-west-2a"
    ):
        """
        Initialize orchestrator
        
        Args:
            region: AWS region
            availability_zone: AZ for EC2 instance (should match FSx AZ)
        """
        self.region = region
        self.availability_zone = availability_zone
        self.ec2_manager = EC2DataPrepManager(
            region=region,
            availability_zone=availability_zone
        )
        
        # Initialize AWS clients
        self.ec2_client = boto3.client('ec2', region_name=region)
        self.fsx_client = boto3.client('fsx', region_name=region)
        
        logger.info(f"Initialized DatasetPreparationOrchestrator")
        logger.info(f"  Region: {region}")
        logger.info(f"  AZ: {availability_zone}")
    
    def get_fsx_info(self, file_system_id: str) -> Dict[str, any]:
        """
        Get FSx file system information
        
        Args:
            file_system_id: FSx file system ID
            
        Returns:
            Dictionary with FSx information
        """
        try:
            response = self.fsx_client.describe_file_systems(
                FileSystemIds=[file_system_id]
            )
            
            if not response['FileSystems']:
                raise ValueError(f"FSx file system not found: {file_system_id}")
            
            fs = response['FileSystems'][0]
            
            # Get SVM information
            svm_response = self.fsx_client.describe_storage_virtual_machines(
                Filters=[
                    {'Name': 'file-system-id', 'Values': [file_system_id]}
                ]
            )
            
            svm_dns = None
            if svm_response['StorageVirtualMachines']:
                svm = svm_response['StorageVirtualMachines'][0]
                endpoints = svm.get('Endpoints', {})
                nfs_endpoints = endpoints.get('Nfs', {})
                svm_dns = nfs_endpoints.get('DNSName')
            
            return {
                'file_system_id': file_system_id,
                'subnet_ids': fs['SubnetIds'],
                'vpc_id': fs['VpcId'],
                'security_group_ids': fs.get('SecurityGroupIds', []),
                'svm_dns': svm_dns
            }
            
        except ClientError as e:
            raise EC2DataPrepError(f"Failed to get FSx info: {e}") from e
    
    def generate_user_data(
        self,
        fsx_dns_name: str,
        fsx_mount_name: str,
        chromosomes: list,
        dest_subdir: str,
        volume_size: str,
        s3_scripts_bucket: Optional[str] = None,
        auto_terminate: bool = True,
        enable_cloudwatch_logs: bool = False
    ) -> str:
        """
        Generate user data script with configuration
        
        Args:
            fsx_dns_name: FSx SVM DNS name
            fsx_mount_name: FSx volume junction path
            chromosomes: List of chromosomes to download
            dest_subdir: Destination subdirectory on FSx
            volume_size: Target dataset size
            s3_scripts_bucket: S3 bucket with scripts (optional)
            auto_terminate: Auto-terminate instance after completion
            enable_cloudwatch_logs: Enable CloudWatch Logs streaming
            
        Returns:
            User data script as string
        """
        # Select user data script based on CloudWatch Logs preference
        if enable_cloudwatch_logs:
            script_path = Path(__file__).parent / "user_data_with_cloudwatch.sh"
        else:
            script_path = Path(__file__).parent / "user_data_script.sh"
        
        if not script_path.exists():
            raise FileNotFoundError(f"User data script not found: {script_path}")
        
        with open(script_path, 'r') as f:
            user_data = f.read()
        
        # Prepend environment variables
        env_vars = f"""#!/bin/bash
# Environment variables for data preparation
export FSX_DNS_NAME="{fsx_dns_name}"
export FSX_MOUNT_NAME="{fsx_mount_name}"
export CHROMOSOMES="{' '.join(chromosomes)}"
export DEST_SUBDIR="{dest_subdir}"
export VOLUME_SIZE="{volume_size}"
export AUTO_TERMINATE="{str(auto_terminate).lower()}"
"""
        
        if s3_scripts_bucket:
            env_vars += f'export S3_SCRIPTS_BUCKET="{s3_scripts_bucket}"\n'
        
        env_vars += "\n"
        
        # Combine environment variables with script
        full_user_data = env_vars + user_data
        
        return full_user_data
    
    def prepare_dataset(
        self,
        fsx_file_system_id: str,
        fsx_mount_name: str,
        chromosomes: list,
        dest_subdir: str,
        volume_size: str,
        s3_scripts_bucket: Optional[str] = None,
        auto_terminate: bool = True,
        monitor_interval: int = 60,
        max_runtime_hours: int = 8,
        enable_cloudwatch_logs: bool = False
    ) -> Dict[str, any]:
        """
        Prepare dataset using EC2 instance
        
        Args:
            fsx_file_system_id: FSx file system ID
            fsx_mount_name: FSx volume junction path (e.g., /genomics)
            chromosomes: List of chromosomes to download
            dest_subdir: Destination subdirectory on FSx
            volume_size: Target dataset size (e.g., "10GB", "100GB")
            s3_scripts_bucket: S3 bucket containing scripts (optional)
            auto_terminate: Auto-terminate instance after completion
            monitor_interval: Monitoring interval in seconds
            max_runtime_hours: Maximum runtime before timeout
            enable_cloudwatch_logs: Enable CloudWatch Logs streaming
            
        Returns:
            Dictionary with preparation results
        """
        instance_id = None
        start_time = time.time()
        max_runtime_seconds = max_runtime_hours * 3600
        
        try:
            # Get FSx information
            logger.info(f"Getting FSx information for {fsx_file_system_id}")
            fsx_info = self.get_fsx_info(fsx_file_system_id)
            
            if not fsx_info['svm_dns']:
                raise EC2DataPrepError("FSx SVM DNS name not found")
            
            logger.info(f"FSx SVM DNS: {fsx_info['svm_dns']}")
            
            # Get subnet in same AZ
            subnet_id = None
            for sid in fsx_info['subnet_ids']:
                response = self.ec2_client.describe_subnets(SubnetIds=[sid])
                subnet = response['Subnets'][0]
                if subnet['AvailabilityZone'] == self.availability_zone:
                    subnet_id = sid
                    break
            
            if not subnet_id:
                raise EC2DataPrepError(
                    f"No subnet found in AZ {self.availability_zone}"
                )
            
            logger.info(f"Using subnet: {subnet_id}")
            
            # Create security group
            security_group_id = self.ec2_manager.create_security_group(
                vpc_id=fsx_info['vpc_id']
            )
            
            # Add ingress rule to FSx security group for NFS from EC2
            if fsx_info['security_group_ids']:
                fsx_sg_id = fsx_info['security_group_ids'][0]
                try:
                    self.ec2_client.authorize_security_group_ingress(
                        GroupId=fsx_sg_id,
                        IpPermissions=[
                            {
                                'IpProtocol': 'tcp',
                                'FromPort': 2049,
                                'ToPort': 2049,
                                'UserIdGroupPairs': [
                                    {'GroupId': security_group_id}
                                ]
                            }
                        ]
                    )
                    logger.info(f"Added NFS ingress rule to FSx security group")
                except ClientError as e:
                    if 'InvalidPermission.Duplicate' in str(e):
                        logger.info("NFS ingress rule already exists")
                    else:
                        raise
            
            # Generate user data script
            if enable_cloudwatch_logs:
                logger.info("Generating user data script with CloudWatch Logs")
            else:
                logger.info("Generating user data script")
            
            user_data = self.generate_user_data(
                fsx_dns_name=fsx_info['svm_dns'],
                fsx_mount_name=fsx_mount_name,
                chromosomes=chromosomes,
                dest_subdir=dest_subdir,
                volume_size=volume_size,
                s3_scripts_bucket=s3_scripts_bucket,
                auto_terminate=auto_terminate,
                enable_cloudwatch_logs=enable_cloudwatch_logs
            )
            
            # Launch EC2 instance
            logger.info("Launching EC2 instance for data preparation")
            instance_info = self.ec2_manager.launch_instance(
                subnet_id=subnet_id,
                security_group_id=security_group_id,
                user_data_script=user_data,
                instance_name=f"data-prep-{dest_subdir}"
            )
            
            instance_id = instance_info['instance_id']
            logger.info(f"Instance launched: {instance_id}")
            
            # Wait for instance to be ready
            logger.info("Waiting for instance to be ready...")
            if not self.ec2_manager.wait_for_ready(instance_id):
                raise EC2DataPrepError("Instance failed to become ready")
            
            logger.info("Instance is ready, data preparation in progress...")
            
            # Monitor progress
            logger.info(f"Monitoring progress (interval: {monitor_interval}s)")
            logger.info(f"Maximum runtime: {max_runtime_hours} hours")
            
            while True:
                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > max_runtime_seconds:
                    raise EC2DataPrepError(
                        f"Data preparation exceeded maximum runtime of {max_runtime_hours} hours"
                    )
                
                # Get instance status
                status = self.ec2_manager.get_instance_status(instance_id)
                
                logger.info(
                    f"Instance state: {status['state']} "
                    f"(elapsed: {elapsed/60:.1f} min)"
                )
                
                # Check if instance terminated (auto-terminate on completion)
                if status['state'] in ['terminated', 'shutting-down']:
                    logger.info("Instance terminated, checking completion status...")
                    
                    # Get console output to check for success
                    console_output = self.ec2_manager.get_console_output(instance_id)
                    
                    if "Data Preparation Completed Successfully" in console_output:
                        logger.info("✓ Data preparation completed successfully")
                        break
                    else:
                        raise EC2DataPrepError(
                            "Instance terminated but completion marker not found"
                        )
                
                # Check if instance stopped (error condition)
                if status['state'] == 'stopped':
                    raise EC2DataPrepError("Instance stopped unexpectedly")
                
                # Wait before next check
                time.sleep(monitor_interval)
            
            # Calculate duration
            duration_seconds = time.time() - start_time
            
            result = {
                'success': True,
                'instance_id': instance_id,
                'duration_seconds': duration_seconds,
                'duration_human': f"{duration_seconds/60:.1f} minutes",
                'volume_size': volume_size,
                'dest_subdir': dest_subdir,
                'chromosomes': chromosomes,
                'completion_time': datetime.utcnow().isoformat() + 'Z'
            }
            
            logger.info("========================================")
            logger.info("Dataset Preparation Complete")
            logger.info(f"  Volume size: {volume_size}")
            logger.info(f"  Destination: {dest_subdir}")
            logger.info(f"  Duration: {result['duration_human']}")
            logger.info("========================================")
            
            return result
            
        except Exception as e:
            logger.error(f"Data preparation failed: {e}")
            
            # Cleanup: terminate instance if it's still running
            if instance_id:
                logger.info(f"Cleaning up: terminating instance {instance_id}")
                self.ec2_manager.terminate_instance(instance_id)
            
            raise
    
    def get_preparation_logs(
        self,
        fsx_mount_point: str,
        dest_subdir: str
    ) -> Dict[str, str]:
        """
        Retrieve preparation logs from FSx volume
        
        Args:
            fsx_mount_point: Local FSx mount point
            dest_subdir: Destination subdirectory
            
        Returns:
            Dictionary mapping log file names to contents
        """
        logs_dir = Path(fsx_mount_point) / dest_subdir / "logs"
        
        if not logs_dir.exists():
            logger.warning(f"Logs directory not found: {logs_dir}")
            return {}
        
        logs = {}
        for log_file in logs_dir.glob("*.log"):
            try:
                with open(log_file, 'r') as f:
                    logs[log_file.name] = f.read()
            except Exception as e:
                logger.error(f"Failed to read log file {log_file}: {e}")
        
        return logs


def main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(
        description="Prepare genomic dataset using EC2 instance"
    )
    
    parser.add_argument(
        '--fsx-file-system-id',
        required=True,
        help='FSx file system ID'
    )
    parser.add_argument(
        '--fsx-mount-name',
        default='/genomics',
        help='FSx volume junction path (default: /genomics)'
    )
    parser.add_argument(
        '--volume-size',
        required=True,
        choices=['10GB', '100GB', '500GB', '1TB', '2TB'],
        help='Target dataset size'
    )
    parser.add_argument(
        '--chromosomes',
        nargs='+',
        required=True,
        help='Chromosomes to download (e.g., chr1 chr2 chrX)'
    )
    parser.add_argument(
        '--dest-subdir',
        required=True,
        help='Destination subdirectory on FSx (e.g., phase_10gb)'
    )
    parser.add_argument(
        '--s3-scripts-bucket',
        help='S3 bucket containing data prep scripts (optional)'
    )
    parser.add_argument(
        '--no-auto-terminate',
        action='store_true',
        help='Do not auto-terminate instance after completion'
    )
    parser.add_argument(
        '--region',
        default='us-west-2',
        help='AWS region (default: us-west-2)'
    )
    parser.add_argument(
        '--availability-zone',
        default='us-west-2a',
        help='Availability zone (default: us-west-2a)'
    )
    parser.add_argument(
        '--monitor-interval',
        type=int,
        default=60,
        help='Monitoring interval in seconds (default: 60)'
    )
    parser.add_argument(
        '--max-runtime-hours',
        type=int,
        default=8,
        help='Maximum runtime in hours (default: 8)'
    )
    parser.add_argument(
        '--enable-cloudwatch-logs',
        action='store_true',
        help='Enable CloudWatch Logs streaming for real-time monitoring'
    )
    parser.add_argument(
        '--output',
        help='Output file for results (JSON format)'
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize orchestrator
        orchestrator = DatasetPreparationOrchestrator(
            region=args.region,
            availability_zone=args.availability_zone
        )
        
        # Prepare dataset
        result = orchestrator.prepare_dataset(
            fsx_file_system_id=args.fsx_file_system_id,
            fsx_mount_name=args.fsx_mount_name,
            chromosomes=args.chromosomes,
            dest_subdir=args.dest_subdir,
            volume_size=args.volume_size,
            s3_scripts_bucket=args.s3_scripts_bucket,
            auto_terminate=not args.no_auto_terminate,
            monitor_interval=args.monitor_interval,
            max_runtime_hours=args.max_runtime_hours,
            enable_cloudwatch_logs=args.enable_cloudwatch_logs
        )
        
        # Save results
        if args.output:
            output_path = Path(args.output)
            with open(output_path, 'w') as f:
                json.dump(result, f, indent=2)
            logger.info(f"Results saved to {output_path}")
        else:
            print(json.dumps(result, indent=2))
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
