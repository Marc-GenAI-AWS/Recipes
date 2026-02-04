#!/usr/bin/env python3
"""
Create IAM role for SageMaker LLM finetuning pipeline.

This script creates an IAM role with minimal required permissions for:
- S3 access (training data and model artifacts)
- SageMaker operations (training, deployment, inference)
- Bedrock access (Claude Sonnet 4 for data generation and judging)
- CloudWatch logging

Usage:
    python create_iam_role.py --bucket-name your-bucket-name
    python create_iam_role.py --bucket-name your-bucket-name --role-name CustomRoleName
    python create_iam_role.py --bucket-name your-bucket-name --enable-vpc
    python create_iam_role.py --bucket-name your-bucket-name --enable-kms --kms-key-arn arn:aws:kms:...
"""

import argparse
import json
import sys
from typing import Dict, Any, Optional

try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
except ImportError:
    print("Error: boto3 is not installed. Install it with: pip install boto3")
    sys.exit(1)


def get_trust_policy(account_id: str) -> Dict[str, Any]:
    """Get the trust policy for SageMaker service."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "sagemaker.amazonaws.com"
                },
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {
                        "aws:SourceAccount": account_id
                    }
                }
            }
        ]
    }


def get_s3_policy(bucket_name: str) -> Dict[str, Any]:
    """Get S3 access policy."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "S3BucketAccess",
                "Effect": "Allow",
                "Action": [
                    "s3:ListBucket",
                    "s3:GetBucketLocation"
                ],
                "Resource": [
                    f"arn:aws:s3:::{bucket_name}"
                ]
            },
            {
                "Sid": "S3ObjectAccess",
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject"
                ],
                "Resource": [
                    f"arn:aws:s3:::{bucket_name}/*"
                ]
            },
            {
                "Sid": "S3ListAllBuckets",
                "Effect": "Allow",
                "Action": [
                    "s3:ListAllMyBuckets"
                ],
                "Resource": "*"
            }
        ]
    }


def get_bedrock_policy() -> Dict[str, Any]:
    """Get Bedrock access policy."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "BedrockModelInvocation",
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                "Resource": [
                    "arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-4-*",
                    "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-*"
                ]
            },
            {
                "Sid": "BedrockModelInfo",
                "Effect": "Allow",
                "Action": [
                    "bedrock:GetFoundationModel",
                    "bedrock:ListFoundationModels"
                ],
                "Resource": "*"
            }
        ]
    }


def get_cloudwatch_policy(account_id: str) -> Dict[str, Any]:
    """Get CloudWatch logs policy."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "CloudWatchLogsAccess",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogStreams"
                ],
                "Resource": [
                    f"arn:aws:logs:*:{account_id}:log-group:/aws/sagemaker/*",
                    f"arn:aws:logs:*:{account_id}:log-group:FinetuningPipeline/*"
                ]
            },
            {
                "Sid": "CloudWatchMetrics",
                "Effect": "Allow",
                "Action": [
                    "cloudwatch:PutMetricData"
                ],
                "Resource": "*",
                "Condition": {
                    "StringEquals": {
                        "cloudwatch:namespace": [
                            "AWS/SageMaker",
                            "FinetuningPipeline/Dev",
                            "FinetuningPipeline/Prod"
                        ]
                    }
                }
            }
        ]
    }


def get_sagemaker_policy(account_id: str) -> Dict[str, Any]:
    """Get SageMaker execution policy."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "SageMakerTraining",
                "Effect": "Allow",
                "Action": [
                    "sagemaker:CreateTrainingJob",
                    "sagemaker:DescribeTrainingJob",
                    "sagemaker:StopTrainingJob",
                    "sagemaker:ListTrainingJobs"
                ],
                "Resource": [
                    f"arn:aws:sagemaker:*:{account_id}:training-job/*"
                ]
            },
            {
                "Sid": "SageMakerModel",
                "Effect": "Allow",
                "Action": [
                    "sagemaker:CreateModel",
                    "sagemaker:DescribeModel",
                    "sagemaker:DeleteModel",
                    "sagemaker:ListModels"
                ],
                "Resource": [
                    f"arn:aws:sagemaker:*:{account_id}:model/*"
                ]
            },
            {
                "Sid": "SageMakerEndpointConfig",
                "Effect": "Allow",
                "Action": [
                    "sagemaker:CreateEndpointConfig",
                    "sagemaker:DescribeEndpointConfig",
                    "sagemaker:DeleteEndpointConfig"
                ],
                "Resource": [
                    f"arn:aws:sagemaker:*:{account_id}:endpoint-config/*"
                ]
            },
            {
                "Sid": "SageMakerEndpoint",
                "Effect": "Allow",
                "Action": [
                    "sagemaker:CreateEndpoint",
                    "sagemaker:DescribeEndpoint",
                    "sagemaker:DeleteEndpoint",
                    "sagemaker:UpdateEndpoint",
                    "sagemaker:InvokeEndpoint",
                    "sagemaker:ListEndpoints"
                ],
                "Resource": [
                    f"arn:aws:sagemaker:*:{account_id}:endpoint/*"
                ]
            },
            {
                "Sid": "SageMakerJumpStart",
                "Effect": "Allow",
                "Action": [
                    "sagemaker:ListModelPackages",
                    "sagemaker:DescribeModelPackage"
                ],
                "Resource": "*"
            },
            {
                "Sid": "ECRAccess",
                "Effect": "Allow",
                "Action": [
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage"
                ],
                "Resource": "*"
            }
        ]
    }


def get_vpc_policy() -> Dict[str, Any]:
    """Get VPC access policy."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "EC2NetworkInterfaces",
                "Effect": "Allow",
                "Action": [
                    "ec2:CreateNetworkInterface",
                    "ec2:CreateNetworkInterfacePermission",
                    "ec2:DeleteNetworkInterface",
                    "ec2:DeleteNetworkInterfacePermission",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:DescribeVpcs",
                    "ec2:DescribeDhcpOptions",
                    "ec2:DescribeSubnets",
                    "ec2:DescribeSecurityGroups"
                ],
                "Resource": "*"
            }
        ]
    }


def get_kms_policy(kms_key_arn: str) -> Dict[str, Any]:
    """Get KMS encryption policy."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "KMSEncryption",
                "Effect": "Allow",
                "Action": [
                    "kms:Decrypt",
                    "kms:Encrypt",
                    "kms:GenerateDataKey",
                    "kms:DescribeKey"
                ],
                "Resource": kms_key_arn
            }
        ]
    }


def create_role(
    iam_client,
    role_name: str,
    bucket_name: str,
    account_id: str,
    enable_vpc: bool = False,
    enable_kms: bool = False,
    kms_key_arn: Optional[str] = None
) -> str:
    """
    Create IAM role with all required policies.
    
    Returns:
        Role ARN
    """
    print(f"Creating IAM role: {role_name}")
    
    # Create role
    try:
        trust_policy = get_trust_policy(account_id)
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Execution role for SageMaker LLM finetuning pipeline with least privilege permissions",
            Tags=[
                {"Key": "Purpose", "Value": "SageMaker-Finetuning"},
                {"Key": "ManagedBy", "Value": "Python-Script"},
                {"Key": "Project", "Value": "LLM-Finetuning-Pipeline"}
            ]
        )
        role_arn = response["Role"]["Arn"]
        print(f"✓ Created role: {role_arn}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            print(f"✓ Role {role_name} already exists")
            response = iam_client.get_role(RoleName=role_name)
            role_arn = response["Role"]["Arn"]
        else:
            raise
    
    # Attach policies
    policies = [
        ("S3AccessPolicy", get_s3_policy(bucket_name)),
        ("BedrockAccessPolicy", get_bedrock_policy()),
        ("CloudWatchLogsPolicy", get_cloudwatch_policy(account_id)),
        ("SageMakerExecutionPolicy", get_sagemaker_policy(account_id))
    ]
    
    if enable_vpc:
        policies.append(("VPCAccessPolicy", get_vpc_policy()))
    
    if enable_kms and kms_key_arn:
        policies.append(("KMSAccessPolicy", get_kms_policy(kms_key_arn)))
    
    for policy_name, policy_document in policies:
        try:
            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName=policy_name,
                PolicyDocument=json.dumps(policy_document)
            )
            print(f"✓ Attached policy: {policy_name}")
        except ClientError as e:
            print(f"✗ Failed to attach policy {policy_name}: {e}")
            raise
    
    return role_arn


def verify_bucket_exists(s3_client, bucket_name: str) -> bool:
    """Verify that the S3 bucket exists."""
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        return True
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "404":
            return False
        elif error_code == "403":
            print(f"Warning: No permission to access bucket {bucket_name}")
            return False
        else:
            raise


def main():
    parser = argparse.ArgumentParser(
        description="Create IAM role for SageMaker LLM finetuning pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python create_iam_role.py --bucket-name my-finetuning-bucket
  
  # Custom role name
  python create_iam_role.py --bucket-name my-bucket --role-name MyCustomRole
  
  # With VPC access
  python create_iam_role.py --bucket-name my-bucket --enable-vpc
  
  # With KMS encryption
  python create_iam_role.py --bucket-name my-bucket --enable-kms --kms-key-arn arn:aws:kms:...
  
  # Specify AWS profile
  python create_iam_role.py --bucket-name my-bucket --profile production
        """
    )
    
    parser.add_argument(
        "--bucket-name",
        required=True,
        help="Name of the S3 bucket for training data and model artifacts"
    )
    parser.add_argument(
        "--role-name",
        default="SageMakerFinetuningRole",
        help="Name for the IAM role (default: SageMakerFinetuningRole)"
    )
    parser.add_argument(
        "--enable-vpc",
        action="store_true",
        help="Enable VPC access for SageMaker"
    )
    parser.add_argument(
        "--enable-kms",
        action="store_true",
        help="Enable KMS encryption for S3"
    )
    parser.add_argument(
        "--kms-key-arn",
        help="ARN of KMS key for S3 encryption (required if --enable-kms is set)"
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)"
    )
    parser.add_argument(
        "--profile",
        help="AWS profile to use (optional)"
    )
    parser.add_argument(
        "--verify-bucket",
        action="store_true",
        help="Verify that the S3 bucket exists before creating role"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.enable_kms and not args.kms_key_arn:
        parser.error("--kms-key-arn is required when --enable-kms is set")
    
    # Create AWS clients
    session_kwargs = {"region_name": args.region}
    if args.profile:
        session_kwargs["profile_name"] = args.profile
    
    try:
        session = boto3.Session(**session_kwargs)
        iam_client = session.client("iam")
        sts_client = session.client("sts")
        s3_client = session.client("s3")
    except (ClientError, BotoCoreError) as e:
        print(f"Error: Failed to create AWS clients: {e}")
        print("\nEnsure AWS credentials are configured:")
        print("  aws configure")
        print("Or set environment variables:")
        print("  export AWS_ACCESS_KEY_ID=...")
        print("  export AWS_SECRET_ACCESS_KEY=...")
        sys.exit(1)
    
    # Get account ID
    try:
        account_id = sts_client.get_caller_identity()["Account"]
        print(f"AWS Account ID: {account_id}")
        print(f"Region: {args.region}")
    except ClientError as e:
        print(f"Error: Failed to get AWS account ID: {e}")
        sys.exit(1)
    
    # Verify bucket exists (optional)
    if args.verify_bucket:
        print(f"\nVerifying S3 bucket: {args.bucket_name}")
        if verify_bucket_exists(s3_client, args.bucket_name):
            print(f"✓ Bucket {args.bucket_name} exists")
        else:
            print(f"✗ Bucket {args.bucket_name} does not exist or is not accessible")
            print(f"\nCreate the bucket with:")
            print(f"  aws s3 mb s3://{args.bucket_name} --region {args.region}")
            sys.exit(1)
    
    # Create role
    print(f"\nCreating IAM role with configuration:")
    print(f"  Role Name: {args.role_name}")
    print(f"  S3 Bucket: {args.bucket_name}")
    print(f"  VPC Access: {args.enable_vpc}")
    print(f"  KMS Encryption: {args.enable_kms}")
    if args.enable_kms:
        print(f"  KMS Key ARN: {args.kms_key_arn}")
    print()
    
    try:
        role_arn = create_role(
            iam_client=iam_client,
            role_name=args.role_name,
            bucket_name=args.bucket_name,
            account_id=account_id,
            enable_vpc=args.enable_vpc,
            enable_kms=args.enable_kms,
            kms_key_arn=args.kms_key_arn
        )
        
        print("\n" + "=" * 80)
        print("SUCCESS! IAM role created successfully")
        print("=" * 80)
        print(f"\nRole ARN: {role_arn}")
        print(f"\nNext steps:")
        print(f"1. Update config/pipeline_config.yaml with:")
        print(f"   aws:")
        print(f"     sagemaker_role_arn: {role_arn}")
        print(f"     s3_bucket: {args.bucket_name}")
        print(f"\n2. Validate permissions:")
        print(f"   python config/aws/scripts/validate_permissions.py --role-arn {role_arn}")
        print(f"\n3. Start using the pipeline!")
        
    except ClientError as e:
        print(f"\n✗ Error creating role: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
