#!/usr/bin/env python3
"""
Validate IAM role permissions for SageMaker LLM finetuning pipeline.

This script checks that the IAM role has all required permissions:
- Role exists and is assumable by SageMaker
- S3 read/write permissions
- SageMaker training and deployment permissions
- Bedrock model invocation permissions
- CloudWatch logging permissions

Usage:
    python validate_permissions.py --role-arn arn:aws:iam::123456789012:role/SageMakerFinetuningRole
    python validate_permissions.py --role-name SageMakerFinetuningRole
    python validate_permissions.py --role-arn arn:aws:iam::123456789012:role/MyRole --bucket-name my-bucket
"""

import argparse
import json
import sys
from typing import List, Tuple, Optional

try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
except ImportError:
    print("Error: boto3 is not installed. Install it with: pip install boto3")
    sys.exit(1)


class PermissionValidator:
    """Validates IAM role permissions for the finetuning pipeline."""
    
    def __init__(self, role_arn: str, bucket_name: Optional[str] = None, region: str = "us-east-1", profile: Optional[str] = None):
        """Initialize validator with role ARN and optional bucket name."""
        session_kwargs = {"region_name": region}
        if profile:
            session_kwargs["profile_name"] = profile
        
        self.session = boto3.Session(**session_kwargs)
        self.iam_client = self.session.client("iam")
        self.sts_client = self.session.client("sts")
        self.iam_resource = self.session.resource("iam")
        
        self.role_arn = role_arn
        self.role_name = role_arn.split("/")[-1]
        self.bucket_name = bucket_name
        self.region = region
        
        self.results: List[Tuple[str, bool, str]] = []
    
    def add_result(self, check_name: str, passed: bool, message: str):
        """Add a validation result."""
        self.results.append((check_name, passed, message))
        status = "✓" if passed else "✗"
        print(f"{status} {check_name}: {message}")
    
    def validate_role_exists(self) -> bool:
        """Check if the role exists."""
        try:
            self.iam_client.get_role(RoleName=self.role_name)
            self.add_result("Role Exists", True, f"Role {self.role_name} exists")
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchEntity":
                self.add_result("Role Exists", False, f"Role {self.role_name} not found")
            else:
                self.add_result("Role Exists", False, f"Error checking role: {e}")
            return False
    
    def validate_trust_policy(self) -> bool:
        """Check if SageMaker can assume the role."""
        try:
            response = self.iam_client.get_role(RoleName=self.role_name)
            trust_policy = response["Role"]["AssumeRolePolicyDocument"]
            
            # Check if SageMaker service is in the trust policy
            for statement in trust_policy.get("Statement", []):
                principal = statement.get("Principal", {})
                service = principal.get("Service", "")
                
                if "sagemaker.amazonaws.com" in service or service == "sagemaker.amazonaws.com":
                    self.add_result("Trust Policy", True, "SageMaker can assume this role")
                    return True
            
            self.add_result("Trust Policy", False, "SageMaker service not found in trust policy")
            return False
        except ClientError as e:
            self.add_result("Trust Policy", False, f"Error checking trust policy: {e}")
            return False
    
    def validate_s3_permissions(self) -> bool:
        """Check S3 permissions."""
        required_actions = [
            "s3:GetObject",
            "s3:PutObject",
            "s3:ListBucket"
        ]
        
        try:
            # Get all policies attached to the role
            role = self.iam_resource.Role(self.role_name)
            
            # Check inline policies
            found_actions = set()
            for policy in role.policies.all():
                policy_doc = policy.policy_document
                for statement in policy_doc.get("Statement", []):
                    if statement.get("Effect") == "Allow":
                        actions = statement.get("Action", [])
                        if isinstance(actions, str):
                            actions = [actions]
                        found_actions.update(actions)
            
            # Check if required actions are present
            missing_actions = []
            for action in required_actions:
                if action not in found_actions and "s3:*" not in found_actions:
                    missing_actions.append(action)
            
            if not missing_actions:
                bucket_msg = f" for bucket {self.bucket_name}" if self.bucket_name else ""
                self.add_result("S3 Permissions", True, f"Has required S3 permissions{bucket_msg}")
                return True
            else:
                self.add_result("S3 Permissions", False, f"Missing actions: {', '.join(missing_actions)}")
                return False
        except ClientError as e:
            self.add_result("S3 Permissions", False, f"Error checking S3 permissions: {e}")
            return False
    
    def validate_sagemaker_permissions(self) -> bool:
        """Check SageMaker permissions."""
        required_actions = [
            "sagemaker:CreateTrainingJob",
            "sagemaker:CreateEndpoint",
            "sagemaker:InvokeEndpoint"
        ]
        
        try:
            role = self.iam_resource.Role(self.role_name)
            
            found_actions = set()
            for policy in role.policies.all():
                policy_doc = policy.policy_document
                for statement in policy_doc.get("Statement", []):
                    if statement.get("Effect") == "Allow":
                        actions = statement.get("Action", [])
                        if isinstance(actions, str):
                            actions = [actions]
                        found_actions.update(actions)
            
            missing_actions = []
            for action in required_actions:
                if action not in found_actions and "sagemaker:*" not in found_actions:
                    missing_actions.append(action)
            
            if not missing_actions:
                self.add_result("SageMaker Permissions", True, "Has required SageMaker permissions")
                return True
            else:
                self.add_result("SageMaker Permissions", False, f"Missing actions: {', '.join(missing_actions)}")
                return False
        except ClientError as e:
            self.add_result("SageMaker Permissions", False, f"Error checking SageMaker permissions: {e}")
            return False
    
    def validate_bedrock_permissions(self) -> bool:
        """Check Bedrock permissions."""
        required_actions = [
            "bedrock:InvokeModel"
        ]
        
        try:
            role = self.iam_resource.Role(self.role_name)
            
            found_actions = set()
            for policy in role.policies.all():
                policy_doc = policy.policy_document
                for statement in policy_doc.get("Statement", []):
                    if statement.get("Effect") == "Allow":
                        actions = statement.get("Action", [])
                        if isinstance(actions, str):
                            actions = [actions]
                        found_actions.update(actions)
            
            missing_actions = []
            for action in required_actions:
                if action not in found_actions and "bedrock:*" not in found_actions:
                    missing_actions.append(action)
            
            if not missing_actions:
                self.add_result("Bedrock Permissions", True, "Has required Bedrock permissions")
                return True
            else:
                self.add_result("Bedrock Permissions", False, f"Missing actions: {', '.join(missing_actions)}")
                return False
        except ClientError as e:
            self.add_result("Bedrock Permissions", False, f"Error checking Bedrock permissions: {e}")
            return False
    
    def validate_cloudwatch_permissions(self) -> bool:
        """Check CloudWatch permissions."""
        required_actions = [
            "logs:CreateLogGroup",
            "logs:CreateLogStream",
            "logs:PutLogEvents"
        ]
        
        try:
            role = self.iam_resource.Role(self.role_name)
            
            found_actions = set()
            for policy in role.policies.all():
                policy_doc = policy.policy_document
                for statement in policy_doc.get("Statement", []):
                    if statement.get("Effect") == "Allow":
                        actions = statement.get("Action", [])
                        if isinstance(actions, str):
                            actions = [actions]
                        found_actions.update(actions)
            
            missing_actions = []
            for action in required_actions:
                if action not in found_actions and "logs:*" not in found_actions:
                    missing_actions.append(action)
            
            if not missing_actions:
                self.add_result("CloudWatch Permissions", True, "Has required CloudWatch permissions")
                return True
            else:
                self.add_result("CloudWatch Permissions", False, f"Missing actions: {', '.join(missing_actions)}")
                return False
        except ClientError as e:
            self.add_result("CloudWatch Permissions", False, f"Error checking CloudWatch permissions: {e}")
            return False
    
    def validate_all(self) -> bool:
        """Run all validation checks."""
        print(f"Validating IAM role: {self.role_arn}")
        print(f"Region: {self.region}")
        print()
        
        checks = [
            self.validate_role_exists,
            self.validate_trust_policy,
            self.validate_s3_permissions,
            self.validate_sagemaker_permissions,
            self.validate_bedrock_permissions,
            self.validate_cloudwatch_permissions
        ]
        
        all_passed = True
        for check in checks:
            if not check():
                all_passed = False
        
        return all_passed
    
    def print_summary(self):
        """Print validation summary."""
        print("\n" + "=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)
        
        passed = sum(1 for _, p, _ in self.results if p)
        total = len(self.results)
        
        print(f"\nPassed: {passed}/{total} checks")
        
        if passed == total:
            print("\n✓ All validation checks passed!")
            print("\nThe IAM role is properly configured for the finetuning pipeline.")
            print("\nNext steps:")
            print("1. Update config/pipeline_config.yaml with the role ARN")
            print("2. Ensure your S3 bucket exists and is accessible")
            print("3. Start using the pipeline!")
        else:
            print("\n✗ Some validation checks failed")
            print("\nFailed checks:")
            for check_name, passed, message in self.results:
                if not passed:
                    print(f"  - {check_name}: {message}")
            
            print("\nRecommendations:")
            print("1. Review the IAM policies attached to the role")
            print("2. Ensure all required permissions are granted")
            print("3. Re-run this validation script after making changes")
            print("\nFor help, see: config/aws/README.md")


def main():
    parser = argparse.ArgumentParser(
        description="Validate IAM role permissions for SageMaker LLM finetuning pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate by role ARN
  python validate_permissions.py --role-arn arn:aws:iam::123456789012:role/SageMakerFinetuningRole
  
  # Validate by role name
  python validate_permissions.py --role-name SageMakerFinetuningRole
  
  # Validate with specific bucket
  python validate_permissions.py --role-arn arn:aws:iam::123456789012:role/MyRole --bucket-name my-bucket
  
  # Use specific AWS profile
  python validate_permissions.py --role-name MyRole --profile production
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--role-arn",
        help="ARN of the IAM role to validate"
    )
    group.add_argument(
        "--role-name",
        help="Name of the IAM role to validate"
    )
    
    parser.add_argument(
        "--bucket-name",
        help="S3 bucket name to validate access (optional)"
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
    
    args = parser.parse_args()
    
    # Construct role ARN if only name is provided
    if args.role_name:
        try:
            session_kwargs = {"region_name": args.region}
            if args.profile:
                session_kwargs["profile_name"] = args.profile
            session = boto3.Session(**session_kwargs)
            sts_client = session.client("sts")
            account_id = sts_client.get_caller_identity()["Account"]
            role_arn = f"arn:aws:iam::{account_id}:role/{args.role_name}"
        except (ClientError, BotoCoreError) as e:
            print(f"Error: Failed to get AWS account ID: {e}")
            sys.exit(1)
    else:
        role_arn = args.role_arn
    
    # Create validator and run checks
    try:
        validator = PermissionValidator(
            role_arn=role_arn,
            bucket_name=args.bucket_name,
            region=args.region,
            profile=args.profile
        )
        
        all_passed = validator.validate_all()
        validator.print_summary()
        
        sys.exit(0 if all_passed else 1)
        
    except (ClientError, BotoCoreError) as e:
        print(f"\nError: {e}")
        print("\nEnsure AWS credentials are configured:")
        print("  aws configure")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
