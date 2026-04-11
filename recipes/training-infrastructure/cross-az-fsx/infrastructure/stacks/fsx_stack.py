"""
FSx stack for cross-AZ FSx SageMaker validation
Creates FSx NetApp ONTAP file system in us-west-2a
"""
from aws_cdk import (
    Stack,
    aws_fsx as fsx,
    aws_ec2 as ec2,
    aws_cloudwatch as cloudwatch,
    CfnOutput,
    RemovalPolicy,
    Duration,
)
from constructs import Construct


class FsxStack(Stack):
    """
    Creates FSx NetApp ONTAP file system:
    - Deployed in single AZ (us-west-2a) to minimize storage costs
    - Configured for NFS access from SageMaker Training Jobs
    - Minimum capacity for testing (1024 GiB SSD, can scale to 800TB)
    - CloudWatch monitoring enabled
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        fsx_subnet: ec2.ISubnet,
        fsx_security_group: ec2.ISecurityGroup,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create FSx NetApp ONTAP file system
        # Using minimum capacity for testing - can be scaled up to 800TB in production
        self.file_system = fsx.CfnFileSystem(
            self,
            "FsxNetAppOntap",
            file_system_type="ONTAP",
            storage_capacity=1024,  # Minimum: 1024 GiB (1 TiB)
            subnet_ids=[fsx_subnet.subnet_id],
            ontap_configuration=fsx.CfnFileSystem.OntapConfigurationProperty(
                deployment_type="SINGLE_AZ_1",
                # Throughput capacity in MBps - 128 is minimum for SINGLE_AZ_1
                throughput_capacity=128,
                preferred_subnet_id=fsx_subnet.subnet_id,
                # Route table IDs for NFS access
                route_table_ids=[],
            ),
            security_group_ids=[fsx_security_group.security_group_id],
            tags=[
                {
                    "key": "Name",
                    "value": "cross-az-fsx-sagemaker-ontap"
                },
                {
                    "key": "Purpose",
                    "value": "Cross-AZ validation testing"
                },
            ],
        )

        # Create Storage Virtual Machine (SVM) for NFS access
        self.storage_virtual_machine = fsx.CfnStorageVirtualMachine(
            self,
            "FsxSvm",
            file_system_id=self.file_system.ref,
            name="svm-genomics",
            # Root volume security style - UNIX for NFS
            root_volume_security_style="UNIX",
        )

        # Create volume for genomic training data
        self.volume = fsx.CfnVolume(
            self,
            "FsxVolume",
            name="genomics_training_data",
            volume_type="ONTAP",
            ontap_configuration=fsx.CfnVolume.OntapConfigurationProperty(
                storage_virtual_machine_id=self.storage_virtual_machine.ref,
                junction_path="/genomics",
                size_in_megabytes="1048576",  # 1 TiB in MiB (1024 * 1024)
                storage_efficiency_enabled="true",
                # NFS export configuration
                tiering_policy=fsx.CfnVolume.TieringPolicyProperty(
                    name="AUTO",
                    cooling_period=31,
                ),
                security_style="UNIX",
            ),
        )

        # CloudWatch Alarms for FSx monitoring
        # Note: FSx for NetApp ONTAP automatically sends metrics to CloudWatch
        # These alarms help monitor performance during cross-AZ validation
        
        # Alarm for high network throughput utilization
        self.network_throughput_alarm = cloudwatch.Alarm(
            self,
            "NetworkThroughputAlarm",
            alarm_name="fsx-cross-az-network-throughput-high",
            alarm_description="Alert when FSx network throughput utilization exceeds 80%",
            metric=cloudwatch.Metric(
                namespace="AWS/FSx",
                metric_name="NetworkThroughputUtilization",
                dimensions_map={
                    "FileSystemId": self.file_system.ref,
                },
                statistic="Average",
                period=Duration.minutes(5),
            ),
            threshold=80,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        )
        
        # Alarm for high CPU utilization
        self.cpu_utilization_alarm = cloudwatch.Alarm(
            self,
            "CpuUtilizationAlarm",
            alarm_name="fsx-cross-az-cpu-utilization-high",
            alarm_description="Alert when FSx CPU utilization exceeds 80%",
            metric=cloudwatch.Metric(
                namespace="AWS/FSx",
                metric_name="CPUUtilization",
                dimensions_map={
                    "FileSystemId": self.file_system.ref,
                },
                statistic="Average",
                period=Duration.minutes(5),
            ),
            threshold=80,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        )
        
        # Alarm for low disk throughput balance (burst credits)
        self.disk_throughput_balance_alarm = cloudwatch.Alarm(
            self,
            "DiskThroughputBalanceAlarm",
            alarm_name="fsx-cross-az-disk-throughput-balance-low",
            alarm_description="Alert when FSx disk throughput burst balance falls below 20%",
            metric=cloudwatch.Metric(
                namespace="AWS/FSx",
                metric_name="FileServerDiskThroughputBalance",
                dimensions_map={
                    "FileSystemId": self.file_system.ref,
                },
                statistic="Average",
                period=Duration.minutes(5),
            ),
            threshold=20,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        
        # Alarm for high disk IOPS utilization
        self.disk_iops_utilization_alarm = cloudwatch.Alarm(
            self,
            "DiskIopsUtilizationAlarm",
            alarm_name="fsx-cross-az-disk-iops-utilization-high",
            alarm_description="Alert when FSx disk IOPS utilization exceeds 80%",
            metric=cloudwatch.Metric(
                namespace="AWS/FSx",
                metric_name="FileServerDiskIopsUtilization",
                dimensions_map={
                    "FileSystemId": self.file_system.ref,
                },
                statistic="Average",
                period=Duration.minutes(5),
            ),
            threshold=80,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        )

        # Outputs
        CfnOutput(
            self,
            "FileSystemId",
            value=self.file_system.ref,
            description="FSx NetApp ONTAP file system ID",
            export_name="FsxFileSystemId",
        )

        CfnOutput(
            self,
            "StorageVirtualMachineId",
            value=self.storage_virtual_machine.ref,
            description="FSx Storage Virtual Machine ID",
            export_name="FsxStorageVirtualMachineId",
        )

        CfnOutput(
            self,
            "VolumeId",
            value=self.volume.ref,
            description="FSx Volume ID for genomics training data",
            export_name="FsxVolumeId",
        )

        CfnOutput(
            self,
            "MountCommand",
            value=f"mount -t nfs <SVM-DNS-NAME>:/genomics /mnt/fsx",
            description="NFS mount command (replace <SVM-DNS-NAME> with actual DNS name from AWS Console)",
        )
        
        CfnOutput(
            self,
            "CloudWatchDashboardUrl",
            value=f"https://console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:",
            description="CloudWatch dashboard URL for FSx metrics monitoring",
        )
