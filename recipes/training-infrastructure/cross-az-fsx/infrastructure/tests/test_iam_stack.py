"""
Unit tests for IAM stack
"""
import aws_cdk as cdk
from aws_cdk.assertions import Template, Match
from stacks.iam_stack import IamStack


def test_sagemaker_execution_role_created():
    """Test that SageMaker execution role is created"""
    app = cdk.App()
    stack = IamStack(app, "TestIamStack", env=cdk.Environment(region="us-west-2"))
    template = Template.from_stack(stack)

    # Verify role exists with correct trust policy
    template.has_resource_properties(
        "AWS::IAM::Role",
        {
            "RoleName": "cross-az-fsx-sagemaker-execution-role",
            "AssumeRolePolicyDocument": {
                "Statement": Match.array_with([
                    {
                        "Action": "sts:AssumeRole",
                        "Effect": "Allow",
                        "Principal": {"Service": "sagemaker.amazonaws.com"},
                    }
                ])
            },
        },
    )


def test_fsx_permissions():
    """Test that FSx permissions are granted"""
    app = cdk.App()
    stack = IamStack(app, "TestIamStack", env=cdk.Environment(region="us-west-2"))
    template = Template.from_stack(stack)

    # Verify FSx policy exists
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": Match.array_with([
                    Match.object_like({
                        "Action": [
                            "fsx:DescribeFileSystems",
                            "fsx:DescribeVolumes",
                            "fsx:DescribeStorageVirtualMachines",
                            "fsx:ListTagsForResource",
                        ],
                        "Effect": "Allow",
                    })
                ])
            }
        },
    )


def test_cloudwatch_logs_permissions():
    """Test that CloudWatch Logs permissions are granted"""
    app = cdk.App()
    stack = IamStack(app, "TestIamStack", env=cdk.Environment(region="us-west-2"))
    template = Template.from_stack(stack)

    # Verify CloudWatch Logs policy exists
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": Match.array_with([
                    Match.object_like({
                        "Action": [
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                            "logs:DescribeLogStreams",
                        ],
                        "Effect": "Allow",
                    })
                ])
            }
        },
    )


def test_cloudwatch_metrics_permissions():
    """Test that CloudWatch Metrics permissions are granted"""
    app = cdk.App()
    stack = IamStack(app, "TestIamStack", env=cdk.Environment(region="us-west-2"))
    template = Template.from_stack(stack)

    # Verify CloudWatch Metrics policy exists
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": Match.array_with([
                    Match.object_like({
                        "Action": "cloudwatch:PutMetricData",
                        "Effect": "Allow",
                        "Condition": {
                            "StringEquals": {
                                "cloudwatch:namespace": "CrossAZValidation"
                            }
                        },
                    })
                ])
            }
        },
    )


def test_s3_permissions():
    """Test that S3 permissions are granted"""
    app = cdk.App()
    stack = IamStack(app, "TestIamStack", env=cdk.Environment(region="us-west-2"))
    template = Template.from_stack(stack)

    # Verify S3 policy exists
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": Match.array_with([
                    Match.object_like({
                        "Action": [
                            "s3:GetObject",
                            "s3:PutObject",
                            "s3:DeleteObject",
                            "s3:ListBucket",
                        ],
                        "Effect": "Allow",
                    })
                ])
            }
        },
    )


def test_ec2_vpc_permissions():
    """Test that EC2 VPC permissions are granted for SageMaker VPC mode"""
    app = cdk.App()
    stack = IamStack(app, "TestIamStack", env=cdk.Environment(region="us-west-2"))
    template = Template.from_stack(stack)

    # Verify EC2 policy exists
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": Match.array_with([
                    Match.object_like({
                        "Action": Match.array_with([
                            "ec2:CreateNetworkInterface",
                            "ec2:DeleteNetworkInterface",
                            "ec2:DescribeNetworkInterfaces",
                        ]),
                        "Effect": "Allow",
                    })
                ])
            }
        },
    )


def test_outputs_exist():
    """Test that stack outputs are created"""
    app = cdk.App()
    stack = IamStack(app, "TestIamStack", env=cdk.Environment(region="us-west-2"))
    template = Template.from_stack(stack)

    # Verify outputs exist
    template.has_output(
        "SageMakerExecutionRoleArn",
        {"Export": {"Name": "SageMakerExecutionRoleArn"}},
    )
    template.has_output(
        "SageMakerExecutionRoleName",
        {"Export": {"Name": "SageMakerExecutionRoleName"}},
    )
