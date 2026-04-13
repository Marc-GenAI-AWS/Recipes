"""
Unit tests for FSx stack
"""
import aws_cdk as cdk
from aws_cdk import assertions
from stacks.network_stack import NetworkStack
from stacks.fsx_stack import FsxStack


def test_fsx_file_system_created():
    """Test that FSx NetApp ONTAP file system is created"""
    app = cdk.App()
    
    # Create network stack first
    network_stack = NetworkStack(
        app,
        "TestNetworkStack",
        env=cdk.Environment(region="us-west-2"),
    )
    
    # Create FSx stack
    fsx_stack = FsxStack(
        app,
        "TestFsxStack",
        vpc=network_stack.vpc,
        fsx_subnet=network_stack.fsx_subnet,
        fsx_security_group=network_stack.fsx_security_group,
        env=cdk.Environment(region="us-west-2"),
    )
    
    # Prepare the stack for assertions
    template = assertions.Template.from_stack(fsx_stack)
    
    # Assert FSx file system is created with correct type
    template.has_resource_properties(
        "AWS::FSx::FileSystem",
        {
            "FileSystemType": "ONTAP",
            "StorageCapacity": 1024,
        }
    )


def test_fsx_storage_virtual_machine_created():
    """Test that Storage Virtual Machine is created"""
    app = cdk.App()
    
    network_stack = NetworkStack(
        app,
        "TestNetworkStack",
        env=cdk.Environment(region="us-west-2"),
    )
    
    fsx_stack = FsxStack(
        app,
        "TestFsxStack",
        vpc=network_stack.vpc,
        fsx_subnet=network_stack.fsx_subnet,
        fsx_security_group=network_stack.fsx_security_group,
        env=cdk.Environment(region="us-west-2"),
    )
    
    template = assertions.Template.from_stack(fsx_stack)
    
    # Assert SVM is created with UNIX security style
    template.has_resource_properties(
        "AWS::FSx::StorageVirtualMachine",
        {
            "Name": "svm-genomics",
            "RootVolumeSecurityStyle": "UNIX",
        }
    )


def test_fsx_volume_created():
    """Test that FSx volume is created with correct configuration"""
    app = cdk.App()
    
    network_stack = NetworkStack(
        app,
        "TestNetworkStack",
        env=cdk.Environment(region="us-west-2"),
    )
    
    fsx_stack = FsxStack(
        app,
        "TestFsxStack",
        vpc=network_stack.vpc,
        fsx_subnet=network_stack.fsx_subnet,
        fsx_security_group=network_stack.fsx_security_group,
        env=cdk.Environment(region="us-west-2"),
    )
    
    template = assertions.Template.from_stack(fsx_stack)
    
    # Assert volume is created with correct properties
    template.has_resource_properties(
        "AWS::FSx::Volume",
        {
            "Name": "genomics_training_data",
            "VolumeType": "ONTAP",
        }
    )


def test_fsx_outputs_exist():
    """Test that required outputs are exported"""
    app = cdk.App()
    
    network_stack = NetworkStack(
        app,
        "TestNetworkStack",
        env=cdk.Environment(region="us-west-2"),
    )
    
    fsx_stack = FsxStack(
        app,
        "TestFsxStack",
        vpc=network_stack.vpc,
        fsx_subnet=network_stack.fsx_subnet,
        fsx_security_group=network_stack.fsx_security_group,
        env=cdk.Environment(region="us-west-2"),
    )
    
    template = assertions.Template.from_stack(fsx_stack)
    
    # Assert required outputs exist
    template.has_output("FileSystemId", {})
    template.has_output("StorageVirtualMachineId", {})
    template.has_output("VolumeId", {})
    template.has_output("MountCommand", {})
    template.has_output("CloudWatchDashboardUrl", {})


def test_cloudwatch_alarms_created():
    """Test that CloudWatch alarms are created for FSx monitoring"""
    app = cdk.App()
    
    network_stack = NetworkStack(
        app,
        "TestNetworkStack",
        env=cdk.Environment(region="us-west-2"),
    )
    
    fsx_stack = FsxStack(
        app,
        "TestFsxStack",
        vpc=network_stack.vpc,
        fsx_subnet=network_stack.fsx_subnet,
        fsx_security_group=network_stack.fsx_security_group,
        env=cdk.Environment(region="us-west-2"),
    )
    
    template = assertions.Template.from_stack(fsx_stack)
    
    # Assert network throughput alarm exists
    template.has_resource_properties(
        "AWS::CloudWatch::Alarm",
        {
            "AlarmName": "fsx-cross-az-network-throughput-high",
            "Threshold": 80,
            "ComparisonOperator": "GreaterThanThreshold",
        }
    )
    
    # Assert CPU utilization alarm exists
    template.has_resource_properties(
        "AWS::CloudWatch::Alarm",
        {
            "AlarmName": "fsx-cross-az-cpu-utilization-high",
            "Threshold": 80,
            "ComparisonOperator": "GreaterThanThreshold",
        }
    )
    
    # Assert disk throughput balance alarm exists
    template.has_resource_properties(
        "AWS::CloudWatch::Alarm",
        {
            "AlarmName": "fsx-cross-az-disk-throughput-balance-low",
            "Threshold": 20,
            "ComparisonOperator": "LessThanThreshold",
        }
    )
    
    # Assert disk IOPS utilization alarm exists
    template.has_resource_properties(
        "AWS::CloudWatch::Alarm",
        {
            "AlarmName": "fsx-cross-az-disk-iops-utilization-high",
            "Threshold": 80,
            "ComparisonOperator": "GreaterThanThreshold",
        }
    )


def test_cloudwatch_alarm_metrics():
    """Test that CloudWatch alarms use correct FSx metrics"""
    app = cdk.App()
    
    network_stack = NetworkStack(
        app,
        "TestNetworkStack",
        env=cdk.Environment(region="us-west-2"),
    )
    
    fsx_stack = FsxStack(
        app,
        "TestFsxStack",
        vpc=network_stack.vpc,
        fsx_subnet=network_stack.fsx_subnet,
        fsx_security_group=network_stack.fsx_security_group,
        env=cdk.Environment(region="us-west-2"),
    )
    
    template = assertions.Template.from_stack(fsx_stack)
    
    # Verify alarms use AWS/FSx namespace
    template.has_resource_properties(
        "AWS::CloudWatch::Alarm",
        assertions.Match.object_like({
            "Namespace": "AWS/FSx",
            "MetricName": "NetworkThroughputUtilization",
        })
    )
    
    template.has_resource_properties(
        "AWS::CloudWatch::Alarm",
        assertions.Match.object_like({
            "Namespace": "AWS/FSx",
            "MetricName": "CPUUtilization",
        })
    )
    
    template.has_resource_properties(
        "AWS::CloudWatch::Alarm",
        assertions.Match.object_like({
            "Namespace": "AWS/FSx",
            "MetricName": "FileServerDiskThroughputBalance",
        })
    )
    
    template.has_resource_properties(
        "AWS::CloudWatch::Alarm",
        assertions.Match.object_like({
            "Namespace": "AWS/FSx",
            "MetricName": "FileServerDiskIopsUtilization",
        })
    )

