#!/usr/bin/env python3
"""
Quick SageMaker Training Job Launcher for Cross-AZ FSx Validation

This script launches a simple SageMaker training job to validate:
1. Cross-AZ FSx mount works (us-west-2a → us-west-2b)
2. Data can be read from the mounted volume
3. Basic metrics collection

This is a simplified version for quick validation before full BioNeMo integration.
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from typing import Dict, Optional

import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SageMakerJobLauncher:
    """Launches SageMaker Training Jobs for cross-AZ FSx validation"""
    
    def __init__(self, region: str = "us-west-2"):
        """
        Initialize launcher
        
        Args:
            region: AWS region
        """
        self.region = region
        self.sagemaker = boto3.client('sagemaker', region_name=region)
        self.ec2 = boto3.client('ec2', region_name=region)
        self.fsx = boto3.client('fsx', region_name=region)
        self.iam = boto3.client('iam', region_name=region)
        
        logger.info(f"Initialized SageMakerJobLauncher in {region}")
    
    def get_fsx_info(self, file_system_id: str) -> Dict[str, any]:
        """
        Get FSx file system information
        
        Args:
            file_system_id: FSx file system ID
            
        Returns:
            Dictionary with FSx information
        """
        try:
            response = self.fsx.describe_file_systems(
                FileSystemIds=[file_system_id]
            )
            
            if not response['FileSystems']:
                raise ValueError(f"FSx file system not found: {file_system_id}")
            
            fs = response['FileSystems'][0]
            
            # Get SVM information
            svm_response = self.fsx.describe_storage_virtual_machines(
                Filters=[
                    {'Name': 'file-system-id', 'Values': [file_system_id]}
                ]
            )
            
            svm_dns = None
            svm_id = None
            if svm_response['StorageVirtualMachines']:
                svm = svm_response['StorageVirtualMachines'][0]
                svm_id = svm['StorageVirtualMachineId']
                endpoints = svm.get('Endpoints', {})
                nfs_endpoints = endpoints.get('Nfs', {})
                svm_dns = nfs_endpoints.get('DNSName')
            
            # Get volume information
            volume_response = self.fsx.describe_volumes(
                Filters=[
                    {'Name': 'file-system-id', 'Values': [file_system_id]}
                ]
            )
            
            volume_id = None
            junction_path = None
            if volume_response['Volumes']:
                volume = volume_response['Volumes'][0]
                volume_id = volume['VolumeId']
                junction_path = volume.get('OntapConfiguration', {}).get('JunctionPath')
            
            return {
                'file_system_id': file_system_id,
                'subnet_ids': fs['SubnetIds'],
                'vpc_id': fs['VpcId'],
                'security_group_ids': fs.get('SecurityGroupIds', []),
                'availability_zone': fs['SubnetIds'][0],  # FSx AZ
                'svm_id': svm_id,
                'svm_dns': svm_dns,
                'volume_id': volume_id,
                'junction_path': junction_path
            }
            
        except ClientError as e:
            logger.error(f"Failed to get FSx info: {e}")
            raise
    
    def get_subnet_in_az(self, vpc_id: str, availability_zone: str) -> Optional[str]:
        """
        Get subnet ID in specified AZ
        
        Args:
            vpc_id: VPC ID
            availability_zone: Target AZ
            
        Returns:
            Subnet ID or None if not found
        """
        try:
            response = self.ec2.describe_subnets(
                Filters=[
                    {'Name': 'vpc-id', 'Values': [vpc_id]},
                    {'Name': 'availability-zone', 'Values': [availability_zone]}
                ]
            )
            
            if response['Subnets']:
                return response['Subnets'][0]['SubnetId']
            
            return None
            
        except ClientError as e:
            logger.error(f"Failed to get subnet: {e}")
            raise
    
    def launch_validation_job(
        self,
        job_name: str,
        fsx_file_system_id: str,
        data_subdir: str,
        target_az: str = "us-west-2b",
        instance_type: str = "ml.m5.xlarge",
        role_arn: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Launch SageMaker training job for cross-AZ validation
        
        Args:
            job_name: Training job name
            fsx_file_system_id: FSx file system ID
            data_subdir: Subdirectory with data (e.g., "phase_10gb")
            target_az: Target availability zone (different from FSx)
            instance_type: SageMaker instance type
            role_arn: IAM role ARN (will use existing if not provided)
            
        Returns:
            Dictionary with job information
        """
        logger.info(f"Launching validation job: {job_name}")
        
        # Get FSx information
        fsx_info = self.get_fsx_info(fsx_file_system_id)
        logger.info(f"FSx AZ: {fsx_info['availability_zone']}")
        logger.info(f"FSx SVM DNS: {fsx_info['svm_dns']}")
        logger.info(f"FSx Junction Path: {fsx_info['junction_path']}")
        
        # Get subnet in target AZ
        subnet_id = self.get_subnet_in_az(fsx_info['vpc_id'], target_az)
        if not subnet_id:
            raise ValueError(f"No subnet found in AZ {target_az}")
        
        logger.info(f"Target AZ: {target_az}")
        logger.info(f"Target Subnet: {subnet_id}")
        
        # Get IAM role
        if not role_arn:
            # Use the existing SageMaker execution role
            role_arn = f"arn:aws:iam::{boto3.client('sts').get_caller_identity()['Account']}:role/cross-az-fsx-sagemaker-execution-role"
        
        logger.info(f"IAM Role: {role_arn}")
        
        # Create training job configuration
        training_job_config = {
            'TrainingJobName': job_name,
            'RoleArn': role_arn,
            'AlgorithmSpecification': {
                'TrainingImage': f"{boto3.client('sts').get_caller_identity()['Account']}.dkr.ecr.{self.region}.amazonaws.com/fsx-validation:latest",
                'TrainingInputMode': 'File',
                'EnableSageMakerMetricsTimeSeries': True
            },
            'ResourceConfig': {
                'InstanceType': instance_type,
                'InstanceCount': 1,
                'VolumeSizeInGB': 50
            },
            'StoppingCondition': {
                'MaxRuntimeInSeconds': 3600  # 1 hour max
            },
            'VpcConfig': {
                'SecurityGroupIds': fsx_info['security_group_ids'],
                'Subnets': [subnet_id]
            },
            'EnableNetworkIsolation': False,
            'EnableInterContainerTrafficEncryption': False,
            'Environment': {
                'FSX_DNS_NAME': fsx_info['svm_dns'],
                'FSX_MOUNT_PATH': fsx_info['junction_path'],
                'DATA_SUBDIR': data_subdir,
                'FSX_AZ': fsx_info['availability_zone'],
                'TRAINING_AZ': target_az
            },
            'Tags': [
                {'Key': 'Purpose', 'Value': 'CrossAZValidation'},
                {'Key': 'DataVolume', 'Value': data_subdir}
            ]
        }
        
        try:
            response = self.sagemaker.create_training_job(**training_job_config)
            
            logger.info(f"✓ Training job launched: {job_name}")
            logger.info(f"  ARN: {response['TrainingJobArn']}")
            
            return {
                'job_name': job_name,
                'job_arn': response['TrainingJobArn'],
                'fsx_az': fsx_info['availability_zone'],
                'training_az': target_az,
                'cross_az': fsx_info['availability_zone'] != target_az,
                'status': 'InProgress'
            }
            
        except ClientError as e:
            logger.error(f"Failed to launch training job: {e}")
            raise
    
    def get_job_status(self, job_name: str) -> Dict[str, any]:
        """
        Get training job status
        
        Args:
            job_name: Training job name
            
        Returns:
            Dictionary with job status
        """
        try:
            response = self.sagemaker.describe_training_job(
                TrainingJobName=job_name
            )
            
            return {
                'job_name': job_name,
                'status': response['TrainingJobStatus'],
                'secondary_status': response.get('SecondaryStatus'),
                'failure_reason': response.get('FailureReason'),
                'creation_time': response['CreationTime'],
                'training_start_time': response.get('TrainingStartTime'),
                'training_end_time': response.get('TrainingEndTime'),
                'billable_time_seconds': response.get('BillableTimeInSeconds'),
                'instance_type': response['ResourceConfig']['InstanceType']
            }
            
        except ClientError as e:
            logger.error(f"Failed to get job status: {e}")
            raise
    
    def wait_for_completion(
        self,
        job_name: str,
        poll_interval: int = 30,
        max_wait_seconds: int = 3600
    ) -> Dict[str, any]:
        """
        Wait for training job to complete
        
        Args:
            job_name: Training job name
            poll_interval: Polling interval in seconds
            max_wait_seconds: Maximum wait time
            
        Returns:
            Final job status
        """
        logger.info(f"Waiting for job completion: {job_name}")
        
        start_time = time.time()
        
        while True:
            elapsed = time.time() - start_time
            
            if elapsed > max_wait_seconds:
                logger.warning(f"Max wait time exceeded ({max_wait_seconds}s)")
                break
            
            status = self.get_job_status(job_name)
            
            logger.info(
                f"Status: {status['status']} | "
                f"Secondary: {status.get('secondary_status', 'N/A')} | "
                f"Elapsed: {elapsed/60:.1f} min"
            )
            
            if status['status'] in ['Completed', 'Failed', 'Stopped']:
                logger.info(f"Job finished with status: {status['status']}")
                return status
            
            time.sleep(poll_interval)
        
        return self.get_job_status(job_name)


def main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(
        description="Launch SageMaker training job for cross-AZ FSx validation"
    )
    
    parser.add_argument(
        '--job-name',
        required=True,
        help='Training job name'
    )
    parser.add_argument(
        '--fsx-file-system-id',
        required=True,
        help='FSx file system ID'
    )
    parser.add_argument(
        '--data-subdir',
        required=True,
        help='Data subdirectory (e.g., phase_10gb)'
    )
    parser.add_argument(
        '--target-az',
        default='us-west-2b',
        help='Target availability zone (default: us-west-2b)'
    )
    parser.add_argument(
        '--instance-type',
        default='ml.m5.xlarge',
        help='SageMaker instance type (default: ml.m5.xlarge)'
    )
    parser.add_argument(
        '--region',
        default='us-west-2',
        help='AWS region (default: us-west-2)'
    )
    parser.add_argument(
        '--wait',
        action='store_true',
        help='Wait for job completion'
    )
    parser.add_argument(
        '--output',
        help='Output file for results (JSON format)'
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize launcher
        launcher = SageMakerJobLauncher(region=args.region)
        
        # Launch job
        result = launcher.launch_validation_job(
            job_name=args.job_name,
            fsx_file_system_id=args.fsx_file_system_id,
            data_subdir=args.data_subdir,
            target_az=args.target_az,
            instance_type=args.instance_type
        )
        
        print(json.dumps(result, indent=2, default=str))
        
        # Wait for completion if requested
        if args.wait:
            final_status = launcher.wait_for_completion(args.job_name)
            result.update(final_status)
        
        # Save results
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            logger.info(f"Results saved to {args.output}")
        
        sys.exit(0 if result.get('status') == 'Completed' else 1)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
