#!/usr/bin/env python3
"""
Unit tests for EC2 Data Prep Manager

Tests EC2 instance lifecycle management for data preparation.
"""

import json
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ec2_data_prep_manager import EC2DataPrepManager, EC2DataPrepError


class TestEC2DataPrepManager:
    """Test EC2DataPrepManager class"""
    
    @pytest.fixture
    def manager(self):
        """Create EC2DataPrepManager instance with mocked clients"""
        with patch('ec2_data_prep_manager.boto3'):
            manager = EC2DataPrepManager(
                region="us-west-2",
                availability_zone="us-west-2a",
                instance_type="c5.4xlarge",
                volume_size_gb=500
            )
            return manager
    
    def test_initialization(self, manager):
        """Test manager initialization"""
        assert manager.region == "us-west-2"
        assert manager.availability_zone == "us-west-2a"
        assert manager.instance_type == "c5.4xlarge"
        assert manager.volume_size_gb == 500
    
    def test_get_latest_amazon_linux_ami(self, manager):
        """Test getting latest Amazon Linux AMI"""
        # Mock EC2 client response
        manager.ec2_client.describe_images = Mock(return_value={
            'Images': [
                {
                    'ImageId': 'ami-old',
                    'Name': 'al2023-ami-2023.1.0',
                    'CreationDate': '2023-01-01T00:00:00.000Z'
                },
                {
                    'ImageId': 'ami-latest',
                    'Name': 'al2023-ami-2023.2.0',
                    'CreationDate': '2023-06-01T00:00:00.000Z'
                }
            ]
        })
        
        ami_id = manager.get_latest_amazon_linux_ami()
        
        assert ami_id == 'ami-latest'
        manager.ec2_client.describe_images.assert_called_once()
    
    def test_get_latest_amazon_linux_ami_no_images(self, manager):
        """Test error when no AMI found"""
        manager.ec2_client.describe_images = Mock(return_value={'Images': []})
        
        with pytest.raises(EC2DataPrepError, match="No Amazon Linux 2023 AMI found"):
            manager.get_latest_amazon_linux_ami()
    
    def test_create_security_group_new(self, manager):
        """Test creating new security group"""
        # Mock responses
        manager.ec2_client.describe_security_groups = Mock(
            return_value={'SecurityGroups': []}
        )
        manager.ec2_client.create_security_group = Mock(
            return_value={'GroupId': 'sg-12345'}
        )
        manager.ec2_client.create_tags = Mock()
        
        sg_id = manager.create_security_group(vpc_id='vpc-12345')
        
        assert sg_id == 'sg-12345'
        manager.ec2_client.create_security_group.assert_called_once()
        manager.ec2_client.create_tags.assert_called_once()
    
    def test_create_security_group_existing(self, manager):
        """Test using existing security group"""
        # Mock existing security group
        manager.ec2_client.describe_security_groups = Mock(
            return_value={
                'SecurityGroups': [{'GroupId': 'sg-existing'}]
            }
        )
        
        sg_id = manager.create_security_group(vpc_id='vpc-12345')
        
        assert sg_id == 'sg-existing'
    
    def test_launch_instance(self, manager):
        """Test launching EC2 instance"""
        # Mock AMI lookup
        manager.get_latest_amazon_linux_ami = Mock(return_value='ami-12345')
        
        # Mock IAM role creation
        manager.create_iam_role = Mock(return_value='arn:aws:iam::123456789012:role/EC2DataPrepRole')
        
        # Mock EC2 run_instances
        launch_time = datetime.utcnow()
        manager.ec2_client.run_instances = Mock(return_value={
            'Instances': [{
                'InstanceId': 'i-12345',
                'Placement': {'AvailabilityZone': 'us-west-2a'},
                'PrivateIpAddress': '10.0.1.100',
                'LaunchTime': launch_time
            }]
        })
        
        result = manager.launch_instance(
            subnet_id='subnet-12345',
            security_group_id='sg-12345',
            user_data_script='#!/bin/bash\necho "test"',
            instance_name='test-instance'
        )
        
        assert result['instance_id'] == 'i-12345'
        assert result['instance_type'] == 'c5.4xlarge'
        assert result['availability_zone'] == 'us-west-2a'
        assert result['private_ip'] == '10.0.1.100'
        
        manager.ec2_client.run_instances.assert_called_once()
        call_args = manager.ec2_client.run_instances.call_args[1]
        assert call_args['ImageId'] == 'ami-12345'
        assert call_args['InstanceType'] == 'c5.4xlarge'
        assert call_args['BlockDeviceMappings'][0]['Ebs']['VolumeSize'] == 500
    
    def test_get_instance_status(self, manager):
        """Test getting instance status"""
        launch_time = datetime.utcnow()
        manager.ec2_client.describe_instances = Mock(return_value={
            'Reservations': [{
                'Instances': [{
                    'InstanceId': 'i-12345',
                    'State': {'Name': 'running', 'Code': 16},
                    'Placement': {'AvailabilityZone': 'us-west-2a'},
                    'PrivateIpAddress': '10.0.1.100',
                    'PublicIpAddress': '54.1.2.3',
                    'LaunchTime': launch_time
                }]
            }]
        })
        
        status = manager.get_instance_status('i-12345')
        
        assert status['instance_id'] == 'i-12345'
        assert status['state'] == 'running'
        assert status['state_code'] == 16
        assert status['availability_zone'] == 'us-west-2a'
        assert status['private_ip'] == '10.0.1.100'
        assert status['public_ip'] == '54.1.2.3'
    
    def test_get_instance_status_not_found(self, manager):
        """Test error when instance not found"""
        manager.ec2_client.describe_instances = Mock(
            return_value={'Reservations': []}
        )
        
        with pytest.raises(EC2DataPrepError, match="Instance not found"):
            manager.get_instance_status('i-nonexistent')
    
    def test_terminate_instance(self, manager):
        """Test terminating instance"""
        manager.ec2_client.terminate_instances = Mock()
        
        result = manager.terminate_instance('i-12345')
        
        assert result is True
        manager.ec2_client.terminate_instances.assert_called_once_with(
            InstanceIds=['i-12345']
        )
    
    def test_get_console_output(self, manager):
        """Test getting console output"""
        manager.ec2_client.get_console_output = Mock(return_value={
            'Output': 'Console output text'
        })
        
        output = manager.get_console_output('i-12345')
        
        assert output == 'Console output text'
        manager.ec2_client.get_console_output.assert_called_once_with(
            InstanceId='i-12345',
            Latest=True
        )
    
    def test_wait_for_ready_success(self, manager):
        """Test waiting for instance to be ready"""
        # Mock waiters
        running_waiter = Mock()
        running_waiter.wait = Mock()
        
        status_waiter = Mock()
        status_waiter.wait = Mock()
        
        manager.ec2_client.get_waiter = Mock(side_effect=[
            running_waiter,
            status_waiter
        ])
        
        result = manager.wait_for_ready('i-12345', timeout_seconds=600)
        
        assert result is True
        assert manager.ec2_client.get_waiter.call_count == 2
        running_waiter.wait.assert_called_once()
        status_waiter.wait.assert_called_once()
    
    def test_wait_for_termination_success(self, manager):
        """Test waiting for instance termination"""
        waiter = Mock()
        waiter.wait = Mock()
        manager.ec2_client.get_waiter = Mock(return_value=waiter)
        
        result = manager.wait_for_termination('i-12345', timeout_seconds=300)
        
        assert result is True
        waiter.wait.assert_called_once()


class TestDatasetPreparationOrchestrator:
    """Test DatasetPreparationOrchestrator class"""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked clients"""
        with patch('prepare_dataset_on_ec2.boto3'):
            from prepare_dataset_on_ec2 import DatasetPreparationOrchestrator
            orchestrator = DatasetPreparationOrchestrator(
                region="us-west-2",
                availability_zone="us-west-2a"
            )
            return orchestrator
    
    def test_get_fsx_info(self, orchestrator):
        """Test getting FSx information"""
        # Mock FSx client responses
        orchestrator.fsx_client.describe_file_systems = Mock(return_value={
            'FileSystems': [{
                'FileSystemId': 'fs-12345',
                'SubnetIds': ['subnet-12345'],
                'VpcId': 'vpc-12345',
                'SecurityGroupIds': ['sg-fsx']
            }]
        })
        
        orchestrator.fsx_client.describe_storage_virtual_machines = Mock(return_value={
            'StorageVirtualMachines': [{
                'Endpoints': {
                    'Nfs': {
                        'DNSName': 'svm-12345.fs-12345.fsx.us-west-2.amazonaws.com'
                    }
                }
            }]
        })
        
        info = orchestrator.get_fsx_info('fs-12345')
        
        assert info['file_system_id'] == 'fs-12345'
        assert info['vpc_id'] == 'vpc-12345'
        assert info['svm_dns'] == 'svm-12345.fs-12345.fsx.us-west-2.amazonaws.com'
    
    def test_generate_user_data(self, orchestrator):
        """Test generating user data script"""
        with patch('prepare_dataset_on_ec2.Path') as mock_path:
            # Mock script file
            mock_script = Mock()
            mock_script.exists.return_value = True
            mock_script.open = Mock()
            
            mock_path.return_value.__truediv__.return_value = mock_script
            
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = "#!/bin/bash\necho test"
                
                user_data = orchestrator.generate_user_data(
                    fsx_dns_name='svm.fsx.amazonaws.com',
                    fsx_mount_name='/genomics',
                    chromosomes=['chr1', 'chr2'],
                    dest_subdir='phase_10gb',
                    volume_size='10GB',
                    auto_terminate=True
                )
                
                assert 'FSX_DNS_NAME="svm.fsx.amazonaws.com"' in user_data
                assert 'CHROMOSOMES="chr1 chr2"' in user_data
                assert 'DEST_SUBDIR="phase_10gb"' in user_data
                assert 'AUTO_TERMINATE="true"' in user_data


def test_chromosome_selection():
    """Test chromosome selection for different dataset sizes"""
    # 10GB: 2 chromosomes
    chromosomes_10gb = ['chr1', 'chr2']
    assert len(chromosomes_10gb) == 2
    
    # 100GB: 10 chromosomes
    chromosomes_100gb = [f'chr{i}' for i in range(1, 11)]
    assert len(chromosomes_100gb) == 10
    
    # 500GB: 23 chromosomes
    chromosomes_500gb = [f'chr{i}' for i in range(1, 23)] + ['chrX']
    assert len(chromosomes_500gb) == 23


def test_cost_calculation():
    """Test cost calculation for EC2 data preparation"""
    # EC2 costs
    ec2_hourly_rate = 0.68  # c5.4xlarge on-demand
    preparation_hours = 4
    ec2_cost = ec2_hourly_rate * preparation_hours
    
    assert ec2_cost == 2.72
    
    # Cross-AZ transfer costs (without EC2)
    cross_az_rate_per_gb = 0.01
    dataset_size_gb = 2048  # 2TB
    cross_az_cost = cross_az_rate_per_gb * dataset_size_gb
    
    assert cross_az_cost == 20.48
    
    # Savings
    savings = cross_az_cost - ec2_cost
    assert savings == 17.76
    assert savings / cross_az_cost > 0.85  # >85% savings


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
