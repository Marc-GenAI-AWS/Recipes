#!/usr/bin/env python3
"""
EC2 Data Preparation Instance Manager

Manages EC2 instance lifecycle for downloading hg38 data and uploading to FSx.
Launches instances in the same AZ as FSx volume to minimize data transfer costs.

This module is part of Phase 2: Data Preparation for cross-AZ FSx validation.
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError, WaiterError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EC2DataPrepError(Exception):
    """Custom exception for EC2 data preparation errors"""
    pass


class EC2DataPrepManager:
    """Manages EC2 instance lifecycle for data preparation"""
    
    def __init__(
        self,
        region: str = "us-west-2",
        availability_zone: str = "us-west-2a",
        instance_type: str = "c6i.4xlarge",
        volume_size_gb: int = 500,
        key_name: Optional[str] = None
    ):
        """
        Initialize EC2 data preparation manager
        
        Args:
            region: AWS region
            availability_zone: AZ for EC2 instance (should match FSx AZ)
            instance_type: EC2 instance type (default: c6i.4xlarge)
            volume_size_gb: EBS volume size for temporary storage
            key_name: SSH key pair name (optional, for debugging)
        """
        self.region = region
        self.availability_zone = availability_zone
        self.instance_type = instance_type
        self.volume_size_gb = volume_size_gb
        self.key_name = key_name
        
        # Initialize AWS clients
        self.ec2_client = boto3.client('ec2', region_name=region)
        self.ec2_resource = boto3.resource('ec2', region_name=region)
        
        logger.info(f"Initialized EC2DataPrepManager")
        logger.info(f"  Region: {region}")
        logger.info(f"  AZ: {availability_zone}")
        logger.info(f"  Instance type: {instance_type}")
        logger.info(f"  Volume size: {volume_size_gb} GB")
    
    def get_latest_amazon_linux_ami(self) -> str:
        """
        Get the latest Amazon Linux 2023 AMI ID
        
        Returns:
            AMI ID string
        """
        try:
            response = self.ec2_client.describe_images(
                Owners=['amazon'],
                Filters=[
                    {
                        'Name': 'name',
                        'Values': ['al2023-ami-2023.*-x86_64']
                    },
                    {
                        'Name': 'state',
                        'Values': ['available']
                    },
                    {
                        'Name': 'architecture',
                        'Values': ['x86_64']
                    }
                ]
            )
            
            # Sort by creation date and get the latest
            images = sorted(
                response['Images'],
                key=lambda x: x['CreationDate'],
                reverse=True
            )
            
            if not images:
                raise EC2DataPrepError("No Amazon Linux 2023 AMI found")
            
            ami_id = images[0]['ImageId']
            logger.info(f"Using AMI: {ami_id} ({images[0]['Name']})")
            
            return ami_id
            
        except ClientError as e:
            raise EC2DataPrepError(f"Failed to get AMI: {e}") from e
    
    def create_security_group(
        self,
        vpc_id: str,
        group_name: str = "ec2-data-prep-sg"
    ) -> str:
        """
        Create security group for EC2 data prep instance
        
        Args:
            vpc_id: VPC ID
            group_name: Security group name
            
        Returns:
            Security group ID
        """
        try:
            # Check if security group already exists
            try:
                response = self.ec2_client.describe_security_groups(
                    Filters=[
                        {'Name': 'group-name', 'Values': [group_name]},
                        {'Name': 'vpc-id', 'Values': [vpc_id]}
                    ]
                )
                
                if response['SecurityGroups']:
                    sg_id = response['SecurityGroups'][0]['GroupId']
                    logger.info(f"Using existing security group: {sg_id}")
                    return sg_id
                    
            except ClientError:
                pass
            
            # Create new security group
            response = self.ec2_client.create_security_group(
                GroupName=group_name,
                Description="Security group for EC2 data preparation instance",
                VpcId=vpc_id
            )
            
            sg_id = response['GroupId']
            logger.info(f"Created security group: {sg_id}")
            
            # Add tags
            self.ec2_client.create_tags(
                Resources=[sg_id],
                Tags=[
                    {'Key': 'Name', 'Value': group_name},
                    {'Key': 'Purpose', 'Value': 'Data preparation for FSx validation'}
                ]
            )
            
            # Allow outbound traffic (default)
            # No inbound rules needed unless SSH access is required
            
            return sg_id
            
        except ClientError as e:
            raise EC2DataPrepError(f"Failed to create security group: {e}") from e

    def create_iam_role(self, role_name: str = "EC2DataPrepRole") -> str:
        """
        Create IAM role for EC2 data prep instance
        
        Args:
            role_name: IAM role name
            
        Returns:
            IAM role ARN
        """
        iam_client = boto3.client('iam', region_name=self.region)
        
        try:
            # Check if role already exists
            try:
                response = iam_client.get_role(RoleName=role_name)
                role_arn = response['Role']['Arn']
                logger.info(f"Using existing IAM role: {role_arn}")
                return role_arn
            except iam_client.exceptions.NoSuchEntityException:
                pass
            
            # Create trust policy for EC2
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "ec2.amazonaws.com"},
                        "Action": "sts:AssumeRole"
                    }
                ]
            }
            
            # Create role
            response = iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description="Role for EC2 data preparation instance"
            )
            
            role_arn = response['Role']['Arn']
            logger.info(f"Created IAM role: {role_arn}")
            
            # Attach policies for FSx, S3, and CloudWatch access
            policies = [
                "arn:aws:iam::aws:policy/AmazonFSxReadOnlyAccess",
                "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy",
                "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
            ]
            
            for policy_arn in policies:
                iam_client.attach_role_policy(
                    RoleName=role_name,
                    PolicyArn=policy_arn
                )
                logger.info(f"Attached policy: {policy_arn}")
            
            # Create inline policy for FSx write access
            fsx_write_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "fsx:DescribeFileSystems",
                            "fsx:DescribeVolumes",
                            "fsx:DescribeStorageVirtualMachines"
                        ],
                        "Resource": "*"
                    }
                ]
            }
            
            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName="FSxAccess",
                PolicyDocument=json.dumps(fsx_write_policy)
            )
            
            # Create instance profile
            try:
                iam_client.create_instance_profile(
                    InstanceProfileName=role_name
                )
                logger.info(f"Created instance profile: {role_name}")
            except iam_client.exceptions.EntityAlreadyExistsException:
                logger.info(f"Instance profile already exists: {role_name}")
            
            # Add role to instance profile
            try:
                iam_client.add_role_to_instance_profile(
                    InstanceProfileName=role_name,
                    RoleName=role_name
                )
            except iam_client.exceptions.LimitExceededException:
                # Role already in instance profile
                pass
            
            # Wait for role to be available
            time.sleep(10)
            
            return role_arn
            
        except ClientError as e:
            raise EC2DataPrepError(f"Failed to create IAM role: {e}") from e
    
    def launch_instance(
        self,
        subnet_id: str,
        security_group_id: str,
        user_data_script: str,
        instance_name: str = "ec2-data-prep-instance"
    ) -> Dict[str, any]:
        """
        Launch EC2 instance for data preparation
        
        Args:
            subnet_id: Subnet ID (should be in same AZ as FSx)
            security_group_id: Security group ID
            user_data_script: User data script content
            instance_name: Name tag for the instance
            
        Returns:
            Dictionary with instance information:
                - instance_id: EC2 instance ID
                - instance_type: Instance type
                - availability_zone: AZ where instance is launched
                - private_ip: Private IP address
                - launch_time: Launch timestamp
        """
        try:
            # Get latest AMI
            ami_id = self.get_latest_amazon_linux_ami()
            
            # Create IAM role
            role_arn = self.create_iam_role()
            role_name = role_arn.split('/')[-1]
            
            # Launch instance
            logger.info(f"Launching EC2 instance: {instance_name}")
            
            launch_params = {
                'ImageId': ami_id,
                'InstanceType': self.instance_type,
                'MinCount': 1,
                'MaxCount': 1,
                'UserData': user_data_script,
                'Monitoring': {
                    'Enabled': True  # Enable detailed monitoring (1-minute intervals)
                },
                'BlockDeviceMappings': [
                    {
                        'DeviceName': '/dev/xvda',
                        'Ebs': {
                            'VolumeSize': self.volume_size_gb,
                            'VolumeType': 'gp3',
                            'DeleteOnTermination': True,
                            'Encrypted': True
                        }
                    }
                ],
                'NetworkInterfaces': [
                    {
                        'DeviceIndex': 0,
                        'SubnetId': subnet_id,
                        'Groups': [security_group_id],
                        'AssociatePublicIpAddress': True
                    }
                ],
                'IamInstanceProfile': {
                    'Name': role_name
                },
                'TagSpecifications': [
                    {
                        'ResourceType': 'instance',
                        'Tags': [
                            {'Key': 'Name', 'Value': instance_name},
                            {'Key': 'Purpose', 'Value': 'Data preparation for FSx validation'},
                            {'Key': 'ManagedBy', 'Value': 'EC2DataPrepManager'}
                        ]
                    }
                ]
            }
            
            # Add key name if provided
            if self.key_name:
                launch_params['KeyName'] = self.key_name
            
            response = self.ec2_client.run_instances(**launch_params)
            
            instance = response['Instances'][0]
            instance_id = instance['InstanceId']
            
            logger.info(f"Launched instance: {instance_id}")
            logger.info(f"  Instance type: {self.instance_type}")
            logger.info(f"  AZ: {instance['Placement']['AvailabilityZone']}")
            
            return {
                'instance_id': instance_id,
                'instance_type': self.instance_type,
                'availability_zone': instance['Placement']['AvailabilityZone'],
                'private_ip': instance.get('PrivateIpAddress', 'pending'),
                'launch_time': instance['LaunchTime'].isoformat()
            }
            
        except ClientError as e:
            raise EC2DataPrepError(f"Failed to launch instance: {e}") from e
    
    def wait_for_ready(
        self,
        instance_id: str,
        timeout_seconds: int = 600
    ) -> bool:
        """
        Wait for EC2 instance to be ready (running and status checks passed)
        
        Args:
            instance_id: EC2 instance ID
            timeout_seconds: Maximum time to wait
            
        Returns:
            True if instance is ready, False if timeout
        """
        try:
            logger.info(f"Waiting for instance {instance_id} to be ready...")
            
            # Wait for instance to be running
            waiter = self.ec2_client.get_waiter('instance_running')
            waiter.wait(
                InstanceIds=[instance_id],
                WaiterConfig={'Delay': 15, 'MaxAttempts': timeout_seconds // 15}
            )
            
            logger.info(f"Instance {instance_id} is running")
            
            # Wait for status checks to pass
            logger.info("Waiting for status checks to pass...")
            waiter = self.ec2_client.get_waiter('instance_status_ok')
            waiter.wait(
                InstanceIds=[instance_id],
                WaiterConfig={'Delay': 15, 'MaxAttempts': timeout_seconds // 15}
            )
            
            logger.info(f"Instance {instance_id} is ready")
            return True
            
        except WaiterError as e:
            logger.error(f"Timeout waiting for instance to be ready: {e}")
            return False
        except ClientError as e:
            logger.error(f"Error waiting for instance: {e}")
            return False
    
    def get_instance_status(self, instance_id: str) -> Dict[str, any]:
        """
        Get current status of EC2 instance
        
        Args:
            instance_id: EC2 instance ID
            
        Returns:
            Dictionary with instance status information
        """
        try:
            response = self.ec2_client.describe_instances(
                InstanceIds=[instance_id]
            )
            
            if not response['Reservations']:
                raise EC2DataPrepError(f"Instance not found: {instance_id}")
            
            instance = response['Reservations'][0]['Instances'][0]
            
            return {
                'instance_id': instance_id,
                'state': instance['State']['Name'],
                'state_code': instance['State']['Code'],
                'availability_zone': instance['Placement']['AvailabilityZone'],
                'private_ip': instance.get('PrivateIpAddress'),
                'public_ip': instance.get('PublicIpAddress'),
                'launch_time': instance['LaunchTime'].isoformat()
            }
            
        except ClientError as e:
            raise EC2DataPrepError(f"Failed to get instance status: {e}") from e
    
    def get_console_output(
        self,
        instance_id: str,
        latest: bool = True
    ) -> str:
        """
        Get console output from EC2 instance
        
        Args:
            instance_id: EC2 instance ID
            latest: If True, return only latest output
            
        Returns:
            Console output as string
        """
        try:
            response = self.ec2_client.get_console_output(
                InstanceId=instance_id,
                Latest=latest
            )
            
            return response.get('Output', '')
            
        except ClientError as e:
            logger.error(f"Failed to get console output: {e}")
            return ""
    
    def terminate_instance(self, instance_id: str) -> bool:
        """
        Terminate EC2 instance
        
        Args:
            instance_id: EC2 instance ID
            
        Returns:
            True if termination initiated successfully
        """
        try:
            logger.info(f"Terminating instance: {instance_id}")
            
            self.ec2_client.terminate_instances(
                InstanceIds=[instance_id]
            )
            
            logger.info(f"Instance {instance_id} termination initiated")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to terminate instance: {e}")
            return False
    
    def wait_for_termination(
        self,
        instance_id: str,
        timeout_seconds: int = 300
    ) -> bool:
        """
        Wait for EC2 instance to be terminated
        
        Args:
            instance_id: EC2 instance ID
            timeout_seconds: Maximum time to wait
            
        Returns:
            True if instance is terminated, False if timeout
        """
        try:
            logger.info(f"Waiting for instance {instance_id} to terminate...")
            
            waiter = self.ec2_client.get_waiter('instance_terminated')
            waiter.wait(
                InstanceIds=[instance_id],
                WaiterConfig={'Delay': 15, 'MaxAttempts': timeout_seconds // 15}
            )
            
            logger.info(f"Instance {instance_id} terminated")
            return True
            
        except WaiterError as e:
            logger.error(f"Timeout waiting for instance termination: {e}")
            return False
        except ClientError as e:
            logger.error(f"Error waiting for termination: {e}")
            return False


def main():
    """Command-line interface for EC2 data prep manager"""
    parser = argparse.ArgumentParser(
        description="Manage EC2 instances for data preparation"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Launch command
    launch_parser = subparsers.add_parser('launch', help='Launch EC2 instance')
    launch_parser.add_argument('--subnet-id', required=True, help='Subnet ID')
    launch_parser.add_argument('--security-group-id', required=True, help='Security group ID')
    launch_parser.add_argument('--user-data', required=True, help='Path to user data script')
    launch_parser.add_argument('--instance-name', default='ec2-data-prep', help='Instance name')
    launch_parser.add_argument('--key-name', help='SSH key pair name')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Get instance status')
    status_parser.add_argument('--instance-id', required=True, help='Instance ID')
    
    # Terminate command
    terminate_parser = subparsers.add_parser('terminate', help='Terminate instance')
    terminate_parser.add_argument('--instance-id', required=True, help='Instance ID')
    terminate_parser.add_argument('--wait', action='store_true', help='Wait for termination')
    
    # Console output command
    console_parser = subparsers.add_parser('console', help='Get console output')
    console_parser.add_argument('--instance-id', required=True, help='Instance ID')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        manager = EC2DataPrepManager()
        
        if args.command == 'launch':
            # Read user data script
            with open(args.user_data, 'r') as f:
                user_data = f.read()
            
            # Launch instance
            result = manager.launch_instance(
                subnet_id=args.subnet_id,
                security_group_id=args.security_group_id,
                user_data_script=user_data,
                instance_name=args.instance_name
            )
            
            print(json.dumps(result, indent=2))
            
            # Wait for ready
            if manager.wait_for_ready(result['instance_id']):
                print(f"\nInstance {result['instance_id']} is ready")
            else:
                print(f"\nWarning: Instance may not be fully ready")
        
        elif args.command == 'status':
            status = manager.get_instance_status(args.instance_id)
            print(json.dumps(status, indent=2))
        
        elif args.command == 'terminate':
            if manager.terminate_instance(args.instance_id):
                if args.wait:
                    manager.wait_for_termination(args.instance_id)
                print(f"Instance {args.instance_id} terminated")
            else:
                print(f"Failed to terminate instance {args.instance_id}")
                sys.exit(1)
        
        elif args.command == 'console':
            output = manager.get_console_output(args.instance_id)
            print(output)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
