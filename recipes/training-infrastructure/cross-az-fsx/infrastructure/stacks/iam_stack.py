"""
IAM stack for cross-AZ FSx SageMaker validation
Creates IAM role for SageMaker Training Jobs with necessary permissions
"""
from aws_cdk import (
    Stack,
    aws_iam as iam,
    CfnOutput,
)
from constructs import Construct


class IamStack(Stack):
    """
    Creates IAM resources for SageMaker Training Jobs:
    - IAM role that SageMaker Training Jobs can assume
    - Permissions for FSx access (read/mount operations)
    - Permissions for CloudWatch Logs (write logs)
    - Permissions for CloudWatch Metrics (publish custom metrics)
    - Permissions for S3 (model artifacts and checkpoints)
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create IAM role for SageMaker Training Jobs
        self.sagemaker_execution_role = iam.Role(
            self,
            "SageMakerExecutionRole",
            role_name="cross-az-fsx-sagemaker-execution-role",
            description="Execution role for SageMaker Training Jobs with FSx and CloudWatch access",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
        )

        # Add FSx permissions for read/mount operations
        fsx_policy = iam.PolicyStatement(
            sid="FsxAccessPermissions",
            effect=iam.Effect.ALLOW,
            actions=[
                "fsx:DescribeFileSystems",
                "fsx:DescribeVolumes",
                "fsx:DescribeStorageVirtualMachines",
                "fsx:ListTagsForResource",
            ],
            resources=["*"],
        )
        self.sagemaker_execution_role.add_to_policy(fsx_policy)

        # Add CloudWatch Logs permissions
        cloudwatch_logs_policy = iam.PolicyStatement(
            sid="CloudWatchLogsPermissions",
            effect=iam.Effect.ALLOW,
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
                "logs:DescribeLogStreams",
            ],
            resources=[
                f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/sagemaker/*",
            ],
        )
        self.sagemaker_execution_role.add_to_policy(cloudwatch_logs_policy)

        # Add CloudWatch Metrics permissions
        cloudwatch_metrics_policy = iam.PolicyStatement(
            sid="CloudWatchMetricsPermissions",
            effect=iam.Effect.ALLOW,
            actions=[
                "cloudwatch:PutMetricData",
            ],
            resources=["*"],
            conditions={
                "StringEquals": {
                    "cloudwatch:namespace": "CrossAZValidation"
                }
            },
        )
        self.sagemaker_execution_role.add_to_policy(cloudwatch_metrics_policy)

        # Add S3 permissions for model artifacts and checkpoints
        s3_policy = iam.PolicyStatement(
            sid="S3AccessPermissions",
            effect=iam.Effect.ALLOW,
            actions=[
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket",
            ],
            resources=[
                "arn:aws:s3:::sagemaker-*/*",
                "arn:aws:s3:::sagemaker-*",
            ],
        )
        self.sagemaker_execution_role.add_to_policy(s3_policy)

        # Add EC2 permissions for VPC access (required for SageMaker VPC mode)
        ec2_policy = iam.PolicyStatement(
            sid="EC2NetworkPermissions",
            effect=iam.Effect.ALLOW,
            actions=[
                "ec2:CreateNetworkInterface",
                "ec2:CreateNetworkInterfacePermission",
                "ec2:DeleteNetworkInterface",
                "ec2:DeleteNetworkInterfacePermission",
                "ec2:DescribeNetworkInterfaces",
                "ec2:DescribeVpcs",
                "ec2:DescribeSubnets",
                "ec2:DescribeSecurityGroups",
                "ec2:DescribeDhcpOptions",
            ],
            resources=["*"],
        )
        self.sagemaker_execution_role.add_to_policy(ec2_policy)

        # Outputs
        CfnOutput(
            self,
            "SageMakerExecutionRoleArn",
            value=self.sagemaker_execution_role.role_arn,
            description="ARN of the SageMaker execution role",
            export_name="SageMakerExecutionRoleArn",
        )

        CfnOutput(
            self,
            "SageMakerExecutionRoleName",
            value=self.sagemaker_execution_role.role_name,
            description="Name of the SageMaker execution role",
            export_name="SageMakerExecutionRoleName",
        )
