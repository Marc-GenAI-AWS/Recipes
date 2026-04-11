"""
Unit tests for P5 instance availability verification

Tests the P5AvailabilityVerifier class to ensure it correctly checks
instance availability for SageMaker Training Jobs.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import sys
import os

# Add parent directory to path to import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verify_p5_availability import P5AvailabilityVerifier


class TestP5AvailabilityVerifier:
    """Test suite for P5AvailabilityVerifier"""
    
    @pytest.fixture
    def verifier(self):
        """Create a verifier instance with mocked AWS clients"""
        with patch('boto3.client'):
            verifier = P5AvailabilityVerifier(region="us-west-2")
            verifier.ec2_client = Mock()
            verifier.sagemaker_client = Mock()
            return verifier
    
    def test_verify_availability_zone_exists(self, verifier):
        """Test that valid availability zone is recognized"""
        verifier.ec2_client.describe_availability_zones.return_value = {
            'AvailabilityZones': [{
                'ZoneName': 'us-west-2b',
                'State': 'available'
            }]
        }
        
        result = verifier._verify_availability_zone('us-west-2b')
        
        assert result is True
        verifier.ec2_client.describe_availability_zones.assert_called_once_with(
            ZoneNames=['us-west-2b']
        )
    
    def test_verify_availability_zone_unavailable(self, verifier):
        """Test that unavailable AZ is detected"""
        verifier.ec2_client.describe_availability_zones.return_value = {
            'AvailabilityZones': [{
                'ZoneName': 'us-west-2b',
                'State': 'unavailable'
            }]
        }
        
        result = verifier._verify_availability_zone('us-west-2b')
        
        assert result is False
    
    def test_verify_availability_zone_not_found(self, verifier):
        """Test that non-existent AZ is detected"""
        verifier.ec2_client.describe_availability_zones.return_value = {
            'AvailabilityZones': []
        }
        
        result = verifier._verify_availability_zone('us-west-2z')
        
        assert result is False
    
    def test_verify_instance_type_supported_p5(self, verifier):
        """Test that P5 instance types are recognized"""
        result = verifier._verify_instance_type_supported('ml.p5.48xlarge')
        assert result is True
    
    def test_verify_instance_type_not_p5(self, verifier):
        """Test that non-P5 instance types are rejected"""
        result = verifier._verify_instance_type_supported('ml.p4d.24xlarge')
        assert result is False
    
    def test_check_ec2_capacity_instance_exists(self, verifier):
        """Test EC2 capacity check when instance type exists"""
        verifier.ec2_client.describe_instance_types.return_value = {
            'InstanceTypes': [{
                'InstanceType': 'p5.48xlarge',
                'VCpuInfo': {'DefaultVCpus': 192},
                'MemoryInfo': {'SizeInMiB': 2097152},
                'GpuInfo': {
                    'Gpus': [{'Name': 'H100', 'Count': 8}]
                }
            }]
        }
        
        result = verifier._check_ec2_capacity('us-west-2b')
        
        assert result['checked'] is True
        assert result['instance_exists'] is True
        verifier.ec2_client.describe_instance_types.assert_called_once_with(
            InstanceTypes=['p5.48xlarge']
        )
    
    def test_check_ec2_capacity_instance_not_found(self, verifier):
        """Test EC2 capacity check when instance type doesn't exist"""
        verifier.ec2_client.describe_instance_types.return_value = {
            'InstanceTypes': []
        }
        
        result = verifier._check_ec2_capacity('us-west-2b')
        
        assert result['checked'] is True
        assert result['instance_exists'] is False
    
    def test_calculate_confidence_high(self, verifier):
        """Test confidence calculation for high confidence scenario"""
        checks = {
            'availability_zone_valid': True,
            'instance_type_supported': True,
            'ec2_capacity_check': {'instance_exists': True}
        }
        
        confidence = verifier._calculate_confidence(checks)
        
        assert confidence == 'HIGH'
    
    def test_calculate_confidence_medium(self, verifier):
        """Test confidence calculation for medium confidence scenario"""
        checks = {
            'availability_zone_valid': True,
            'instance_type_supported': True,
            'ec2_capacity_check': {'instance_exists': False}
        }
        
        confidence = verifier._calculate_confidence(checks)
        
        assert confidence == 'MEDIUM'
    
    def test_calculate_confidence_low(self, verifier):
        """Test confidence calculation for low confidence scenario"""
        checks = {
            'availability_zone_valid': False,
            'instance_type_supported': True
        }
        
        confidence = verifier._calculate_confidence(checks)
        
        assert confidence == 'LOW'
    
    def test_verify_p5_availability_success(self, verifier):
        """Test full verification with successful result"""
        # Mock all the checks to return success
        verifier.ec2_client.describe_availability_zones.return_value = {
            'AvailabilityZones': [{
                'ZoneName': 'us-west-2b',
                'State': 'available'
            }]
        }
        
        verifier.ec2_client.describe_instance_types.return_value = {
            'InstanceTypes': [{
                'InstanceType': 'p5.48xlarge',
                'VCpuInfo': {'DefaultVCpus': 192},
                'MemoryInfo': {'SizeInMiB': 2097152},
                'GpuInfo': {'Gpus': [{'Name': 'H100'}]}
            }]
        }
        
        result = verifier.verify_p5_availability(
            availability_zone='us-west-2b',
            instance_type='ml.p5.48xlarge'
        )
        
        assert result['available'] is True
        assert result['confidence'] == 'HIGH'
        assert result['region'] == 'us-west-2'
        assert result['availability_zone'] == 'us-west-2b'
        assert result['instance_type'] == 'ml.p5.48xlarge'
        assert 'timestamp' in result
        assert 'checks' in result
    
    def test_verify_p5_availability_invalid_az(self, verifier):
        """Test verification with invalid availability zone"""
        verifier.ec2_client.describe_availability_zones.return_value = {
            'AvailabilityZones': []
        }
        
        result = verifier.verify_p5_availability(
            availability_zone='us-west-2z',
            instance_type='ml.p5.48xlarge'
        )
        
        assert result['available'] is False
        assert 'does not exist' in result['reason']
    
    def test_verify_p5_availability_unsupported_instance(self, verifier):
        """Test verification with unsupported instance type"""
        verifier.ec2_client.describe_availability_zones.return_value = {
            'AvailabilityZones': [{
                'ZoneName': 'us-west-2b',
                'State': 'available'
            }]
        }
        
        result = verifier.verify_p5_availability(
            availability_zone='us-west-2b',
            instance_type='ml.p4d.24xlarge'
        )
        
        assert result['available'] is False
        assert 'not supported' in result['reason']
    
    def test_export_results(self, verifier, tmp_path):
        """Test exporting results to JSON file"""
        result = {
            'available': True,
            'confidence': 'HIGH',
            'region': 'us-west-2',
            'availability_zone': 'us-west-2b'
        }
        
        output_file = tmp_path / "test_results.json"
        verifier.export_results(result, str(output_file))
        
        assert output_file.exists()
        
        with open(output_file, 'r') as f:
            loaded_result = json.load(f)
        
        assert loaded_result == result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
