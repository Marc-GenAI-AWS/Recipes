#!/usr/bin/env python3
"""
AWS CDK app for cross-AZ FSx SageMaker validation infrastructure
"""
import aws_cdk as cdk
from stacks.network_stack import NetworkStack
from stacks.iam_stack import IamStack
from stacks.fsx_stack import FsxStack
from stacks.lustre_stack import LustreStack

app = cdk.App()

# Create network stack first
network_stack = NetworkStack(
    app,
    "CrossAzFsxSageMakerNetwork",
    env=cdk.Environment(region="us-west-2"),
    description="VPC and networking for cross-AZ FSx SageMaker validation"
)

# Create IAM stack
iam_stack = IamStack(
    app,
    "CrossAzFsxSageMakerIam",
    env=cdk.Environment(region="us-west-2"),
    description="IAM role for SageMaker Training Jobs with FSx and CloudWatch access"
)

# Create FSx stack - depends on network stack
fsx_stack = FsxStack(
    app,
    "CrossAzFsxSageMakerFsx",
    vpc=network_stack.vpc,
    fsx_subnet=network_stack.fsx_subnet,
    fsx_security_group=network_stack.fsx_security_group,
    env=cdk.Environment(region="us-west-2"),
    description="FSx NetApp ONTAP file system in us-west-2a for genomics training data"
)
fsx_stack.add_dependency(network_stack)

# FSx for Lustre stack — alternative to NetApp ONTAP for SageMaker native support
lustre_stack = LustreStack(
    app,
    "CrossAzFsxSageMakerLustre",
    vpc=network_stack.vpc,
    fsx_subnet=network_stack.fsx_subnet,
    sagemaker_security_group=network_stack.sagemaker_security_group,
    ec2_data_prep_security_group=network_stack.ec2_data_prep_security_group,
    env=cdk.Environment(region="us-west-2"),
    description="FSx for Lustre (SCRATCH_2) in us-west-2a for SageMaker cross-AZ validation",
)
lustre_stack.add_dependency(network_stack)

app.synth()
