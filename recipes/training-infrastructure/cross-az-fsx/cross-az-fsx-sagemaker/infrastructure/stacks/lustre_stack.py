"""
FSx for Lustre stack for SageMaker cross-AZ validation.

Deploys an FSx Lustre filesystem in the FSx subnet (AZ configured via FSX_AZ
in .env).  SageMaker training jobs mount it natively via FileSystemConfig —
no manual mount, no container capabilities needed.

Deployment type and storage capacity are injected by the CDK app from
config.py, so switching from SCRATCH_2 (validation) to PERSISTENT_2
(production) requires only a .env change and a CDK update.
"""

from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_fsx as fsx,
    CfnOutput,
    RemovalPolicy,
)
from constructs import Construct


class LustreStack(Stack):
    """
    Creates:
    - Security group allowing Lustre client traffic (tcp 988, 1018-1023) from
      SageMaker training jobs + EC2 data prep instances.
    - FSx for Lustre filesystem (SCRATCH_2, 1200 GiB min) in the FSx subnet.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        fsx_subnet: ec2.ISubnet,
        sagemaker_security_group: ec2.ISecurityGroup,
        ec2_data_prep_security_group: ec2.ISecurityGroup,
        storage_capacity_gb: int = 1200,
        deployment_type: str = "SCRATCH_2",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Lustre client uses TCP 988 plus the 1018-1023 range for data.
        self.lustre_security_group = ec2.SecurityGroup(
            self,
            "LustreSecurityGroup",
            vpc=vpc,
            security_group_name="fsx-lustre-sg",
            description="FSx for Lustre - allow Lustre client traffic from SageMaker + EC2 prep",
            allow_all_outbound=True,
        )

        for peer in (sagemaker_security_group, ec2_data_prep_security_group):
            self.lustre_security_group.add_ingress_rule(
                peer=peer,
                connection=ec2.Port.tcp(988),
                description=f"Lustre client (tcp 988) from {peer.security_group_id}",
            )
            self.lustre_security_group.add_ingress_rule(
                peer=peer,
                connection=ec2.Port.tcp_range(1018, 1023),
                description=f"Lustre data (tcp 1018-1023) from {peer.security_group_id}",
            )
        # Lustre clients also need to reach each other on these ports for
        # peer-to-peer RPC; Lustre mount helpers check this. Add self-reference.
        self.lustre_security_group.add_ingress_rule(
            peer=self.lustre_security_group,
            connection=ec2.Port.tcp(988),
            description="Lustre client self (tcp 988)",
        )
        self.lustre_security_group.add_ingress_rule(
            peer=self.lustre_security_group,
            connection=ec2.Port.tcp_range(1018, 1023),
            description="Lustre client self (tcp 1018-1023)",
        )

        # FSx for Lustre filesystem (Lustre 2.15 explicitly pinned).
        # AWS defaults SCRATCH_2 to Lustre 2.10, which is incompatible with
        # modern client packages shipped on DLAMI and SageMaker images.
        # Always force 2.15.
        self.file_system = fsx.CfnFileSystem(
            self,
            "LustreFileSystem",
            file_system_type="LUSTRE",
            file_system_type_version="2.15",
            storage_capacity=storage_capacity_gb,
            subnet_ids=[fsx_subnet.subnet_id],
            security_group_ids=[self.lustre_security_group.security_group_id],
            lustre_configuration=fsx.CfnFileSystem.LustreConfigurationProperty(
                deployment_type=deployment_type,
            ),
            tags=[
                {"key": "Name", "value": "cross-az-fsx-lustre"},
                {"key": "Purpose", "value": "SageMaker cross-AZ validation"},
                {"key": "DeploymentType", "value": deployment_type},
                {"key": "StorageCapacityGiB", "value": str(storage_capacity_gb)},
            ],
        )
        self.file_system.apply_removal_policy(RemovalPolicy.DESTROY)

        CfnOutput(
            self,
            "LustreFileSystemId",
            value=self.file_system.ref,
            export_name="LustreFileSystemId",
        )
        CfnOutput(
            self,
            "LustreSecurityGroupId",
            value=self.lustre_security_group.security_group_id,
            export_name="LustreSecurityGroupId",
        )
        CfnOutput(
            self,
            "LustreMountName",
            value=self.file_system.attr_lustre_mount_name,
            export_name="LustreMountName",
            description="Lustre mount name suffix, used as filesystem_name:/<mount_name>",
        )
        CfnOutput(
            self,
            "LustreDnsName",
            value=self.file_system.attr_dns_name,
            export_name="LustreDnsName",
        )
