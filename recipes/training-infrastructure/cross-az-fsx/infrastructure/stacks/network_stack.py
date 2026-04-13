"""
Network stack for cross-AZ FSx + SageMaker validation.

Creates a VPC with two public subnets — one per AZ — plus security groups
and an S3 gateway endpoint.  The AZs are injected by the CDK app (via
config.py) so the same stack works for any region/AZ combination.
"""
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    CfnOutput,
)
from constructs import Construct


class NetworkStack(Stack):
    """
    Creates:
    - VPC with subnets in fsx_az (holds the Lustre FS) and sagemaker_az
      (hosts SageMaker training jobs).
    - Security groups for SageMaker training jobs and EC2 data-prep instances.
    - S3 gateway endpoint (required for VPC-mode SageMaker to reach S3).

    Args:
        fsx_az:       AZ for the FSx Lustre subnet (e.g. "us-west-2a")
        sagemaker_az: AZ for the SageMaker training subnet (e.g. "us-west-2c")
        vpc_cidr:     VPC CIDR block (default "10.0.0.0/16")
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        fsx_az: str,
        sagemaker_az: str,
        vpc_cidr: str = "10.0.0.0/16",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self._fsx_az = fsx_az
        self._sagemaker_az = sagemaker_az

        # Include both AZs; CDK needs the full list up front.
        # We deduplicate in case fsx_az == sagemaker_az (same-AZ mode).
        azs = list(dict.fromkeys([fsx_az, sagemaker_az]))

        self.vpc = ec2.Vpc(
            self,
            "CrossAzVpc",
            vpc_name="cross-az-fsx-sagemaker-vpc",
            ip_addresses=ec2.IpAddresses.cidr(vpc_cidr),
            availability_zones=azs,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                    map_public_ip_on_launch=False,
                ),
            ],
        )

        # Locate subnets by AZ. CDK creates one subnet per AZ in the order
        # specified above, so we match by availability_zone rather than index.
        self.fsx_subnet = None
        self.sagemaker_subnet = None

        for subnet in self.vpc.public_subnets:
            if subnet.availability_zone == fsx_az:
                self.fsx_subnet = subnet
            if subnet.availability_zone == sagemaker_az:
                self.sagemaker_subnet = subnet

        # Fallback: same-AZ mode — both point to the single subnet.
        if self.fsx_subnet is None:
            self.fsx_subnet = self.vpc.public_subnets[0]
        if self.sagemaker_subnet is None:
            self.sagemaker_subnet = self.vpc.public_subnets[0]

        # Security group for SageMaker Training Jobs.
        # The Lustre stack adds ingress rules on ports 988 and 1018-1023
        # from this SG to the Lustre SG.
        self.sagemaker_security_group = ec2.SecurityGroup(
            self,
            "SageMakerSecurityGroup",
            vpc=self.vpc,
            security_group_name="sagemaker-training-sg",
            description=(
                f"SageMaker training jobs in {sagemaker_az} — "
                "allows Lustre client traffic to FSx"
            ),
            allow_all_outbound=True,
        )

        # Security group for throwaway EC2 data-prep instances.
        # Used by scripts in data_preparation/ that mount Lustre and stage data.
        self.ec2_data_prep_security_group = ec2.SecurityGroup(
            self,
            "Ec2DataPrepSecurityGroup",
            vpc=self.vpc,
            security_group_name="ec2-data-prep-sg",
            description="EC2 data-preparation instances — outbound only, SSM access",
            allow_all_outbound=True,
        )

        # S3 Gateway endpoint — required for VPC-attached SageMaker training
        # jobs to reach S3 (input channels, output, model artifacts) without
        # a NAT gateway or public IP.
        self.s3_endpoint = self.vpc.add_gateway_endpoint(
            "S3GatewayEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
        )

        # ── Outputs ────────────────────────────────────────────────────────────

        CfnOutput(self, "VpcId",
                  value=self.vpc.vpc_id,
                  description="VPC ID")

        CfnOutput(self, "FsxAz",
                  value=fsx_az,
                  description="AZ where the FSx Lustre filesystem lives")

        CfnOutput(self, "SageMakerAz",
                  value=sagemaker_az,
                  description="AZ where SageMaker training jobs run")

        CfnOutput(self, "FsxSubnetId",
                  value=self.fsx_subnet.subnet_id,
                  description=f"Subnet ID in {fsx_az} (holds the Lustre filesystem)")

        CfnOutput(self, "SageMakerSubnetId",
                  value=self.sagemaker_subnet.subnet_id,
                  description=f"Subnet ID in {sagemaker_az} (hosts SageMaker training jobs)")

        CfnOutput(self, "FsxSubnetCidr",
                  value=self.fsx_subnet.ipv4_cidr_block,
                  description=f"CIDR for the FSx subnet ({fsx_az})")

        CfnOutput(self, "SageMakerSubnetCidr",
                  value=self.sagemaker_subnet.ipv4_cidr_block,
                  description=f"CIDR for the SageMaker subnet ({sagemaker_az})")

        CfnOutput(self, "SageMakerSecurityGroupId",
                  value=self.sagemaker_security_group.security_group_id,
                  description="Security group ID for SageMaker Training Jobs")

        CfnOutput(self, "Ec2DataPrepSecurityGroupId",
                  value=self.ec2_data_prep_security_group.security_group_id,
                  description="Security group ID for EC2 data-preparation instances",
                  export_name="Ec2DataPrepSecurityGroupId")
