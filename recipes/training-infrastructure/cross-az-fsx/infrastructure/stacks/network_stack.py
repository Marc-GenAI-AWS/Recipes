"""
Network stack for cross-AZ FSx SageMaker validation
Creates VPC with subnets in us-west-2a and us-west-2b
"""
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    CfnOutput,
)
from constructs import Construct


class NetworkStack(Stack):
    """
    Creates VPC infrastructure for cross-AZ validation:
    - VPC with 10.0.0.0/16 CIDR
    - Subnet in us-west-2a for FSx NetApp ONTAP
    - Subnet in us-west-2b for P5 SageMaker Training Jobs
    - Internet Gateway for external access
    - Route tables for both subnets
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create VPC with explicit AZ configuration
        self.vpc = ec2.Vpc(
            self,
            "CrossAzVpc",
            vpc_name="cross-az-fsx-sagemaker-vpc",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            availability_zones=["us-west-2a", "us-west-2b"],
            nat_gateways=0,  # No NAT gateway needed for this validation
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                    map_public_ip_on_launch=False,
                ),
            ],
        )

        # Get subnets by AZ
        # CDK creates subnets in the order specified in availability_zones
        # us-west-2a will be first, us-west-2b will be second
        self.fsx_subnet = None
        self.sagemaker_subnet = None
        
        for subnet in self.vpc.public_subnets:
            az = subnet.availability_zone
            if az == "us-west-2a":
                self.fsx_subnet = subnet
            elif az == "us-west-2b":
                self.sagemaker_subnet = subnet
        
        # Fallback: if specific AZs not found, use first two subnets
        if self.fsx_subnet is None and len(self.vpc.public_subnets) >= 1:
            self.fsx_subnet = self.vpc.public_subnets[0]
        if self.sagemaker_subnet is None and len(self.vpc.public_subnets) >= 2:
            self.sagemaker_subnet = self.vpc.public_subnets[1]

        # Create security group for FSx NetApp ONTAP
        self.fsx_security_group = ec2.SecurityGroup(
            self,
            "FsxSecurityGroup",
            vpc=self.vpc,
            security_group_name="fsx-netapp-ontap-sg",
            description="Security group for FSx NetApp ONTAP - allows NFS access from SageMaker",
            allow_all_outbound=True,
        )

        # Create security group for SageMaker Training Jobs
        self.sagemaker_security_group = ec2.SecurityGroup(
            self,
            "SageMakerSecurityGroup",
            vpc=self.vpc,
            security_group_name="sagemaker-training-sg",
            description="Security group for SageMaker Training Jobs - allows NFS access to FSx",
            allow_all_outbound=True,
        )

        # Allow NFS traffic (port 2049) from SageMaker to FSx
        self.fsx_security_group.add_ingress_rule(
            peer=self.sagemaker_security_group,
            connection=ec2.Port.tcp(2049),
            description="Allow NFS access from SageMaker Training Jobs",
        )

        # Allow NFS traffic (port 2049) from FSx to SageMaker (for bidirectional communication)
        self.sagemaker_security_group.add_ingress_rule(
            peer=self.fsx_security_group,
            connection=ec2.Port.tcp(2049),
            description="Allow NFS responses from FSx NetApp ONTAP",
        )

        # Outputs
        CfnOutput(
            self,
            "VpcId",
            value=self.vpc.vpc_id,
            description="VPC ID for cross-AZ validation",
        )

        CfnOutput(
            self,
            "FsxSubnetId",
            value=self.fsx_subnet.subnet_id if self.fsx_subnet else "Not found",
            description="Subnet ID in us-west-2a for FSx NetApp ONTAP",
        )

        CfnOutput(
            self,
            "SageMakerSubnetId",
            value=self.sagemaker_subnet.subnet_id if self.sagemaker_subnet else "Not found",
            description="Subnet ID in us-west-2b for SageMaker Training Jobs",
        )

        CfnOutput(
            self,
            "FsxSubnetCidr",
            value=self.fsx_subnet.ipv4_cidr_block if self.fsx_subnet else "Not found",
            description="CIDR block for FSx subnet",
        )

        CfnOutput(
            self,
            "SageMakerSubnetCidr",
            value=self.sagemaker_subnet.ipv4_cidr_block if self.sagemaker_subnet else "Not found",
            description="CIDR block for SageMaker subnet",
        )

        CfnOutput(
            self,
            "FsxSecurityGroupId",
            value=self.fsx_security_group.security_group_id,
            description="Security group ID for FSx NetApp ONTAP",
        )

        CfnOutput(
            self,
            "SageMakerSecurityGroupId",
            value=self.sagemaker_security_group.security_group_id,
            description="Security group ID for SageMaker Training Jobs",
        )
