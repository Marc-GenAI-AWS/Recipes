#!/usr/bin/env python3
"""
Clean up IAM role for SageMaker LLM finetuning pipeline.

This script safely deletes the IAM role and all attached policies.
It will:
1. List all inline policies attached to the role
2. Delete all inline policies
3. Detach all managed policies
4. Delete the role

Usage:
    python cleanup_role.py --role-name SageMakerFinetuningRole
    python cleanup_role.py --role-arn arn:aws:iam::123456789012:role/SageMakerFinetuningRole
    python cleanup_role.py --role-name MyRole --force  # Skip confirmation
"""

import argparse
import sys
from typing import Optional

try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
except ImportError:
    print("Error: boto3 is not installed. Install it with: pip install boto3")
    sys.exit(1)


def confirm_deletion(role_name: str) -> bool:
    """Ask user to confirm role deletion."""
    print(f"\n⚠️  WARNING: This will permanently delete the IAM role '{role_name}'")
    print("This action cannot be undone.")
    print("\nEnsure that:")
    print("  - No SageMaker jobs are currently using this role")
    print("  - No other services depend on this role")
    print("  - You have a backup of the role configuration if needed")
    
    response = input("\nAre you sure you want to delete this role? (yes/no): ")
    return response.lower() in ["yes", "y"]


def delete_inline_policies(iam_client, role_name: str) -> int:
    """Delete all inline policies attached to the role."""
    try:
        response = iam_client.list_role_policies(RoleName=role_name)
        policy_names = response.get("PolicyNames", [])
        
        if not policy_names:
            print("  No inline policies to delete")
            return 0
        
        for policy_name in policy_names:
            iam_client.delete_role_policy(
                RoleName=role_name,
                PolicyName=policy_name
            )
            print(f"  ✓ Deleted inline policy: {policy_name}")
        
        return len(policy_names)
    except ClientError as e:
        print(f"  ✗ Error deleting inline policies: {e}")
        raise


def detach_managed_policies(iam_client, role_name: str) -> int:
    """Detach all managed policies from the role."""
    try:
        response = iam_client.list_attached_role_policies(RoleName=role_name)
        policies = response.get("AttachedPolicies", [])
        
        if not policies:
            print("  No managed policies to detach")
            return 0
        
        for policy in policies:
            iam_client.detach_role_policy(
                RoleName=role_name,
                PolicyArn=policy["PolicyArn"]
            )
            print(f"  ✓ Detached managed policy: {policy['PolicyName']}")
        
        return len(policies)
    except ClientError as e:
        print(f"  ✗ Error detaching managed policies: {e}")
        raise


def delete_role(iam_client, role_name: str) -> bool:
    """Delete the IAM role."""
    try:
        iam_client.delete_role(RoleName=role_name)
        print(f"  ✓ Deleted role: {role_name}")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            print(f"  ✗ Role {role_name} does not exist")
        else:
            print(f"  ✗ Error deleting role: {e}")
        return False


def cleanup_role(
    iam_client,
    role_name: str,
    force: bool = False
) -> bool:
    """
    Clean up IAM role and all attached policies.
    
    Returns:
        True if successful, False otherwise
    """
    # Check if role exists
    try:
        iam_client.get_role(RoleName=role_name)
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            print(f"✗ Role {role_name} does not exist")
            return False
        else:
            print(f"✗ Error checking role: {e}")
            return False
    
    # Confirm deletion
    if not force:
        if not confirm_deletion(role_name):
            print("\nDeletion cancelled")
            return False
    
    print(f"\nCleaning up IAM role: {role_name}")
    
    # Delete inline policies
    print("\n1. Deleting inline policies...")
    try:
        inline_count = delete_inline_policies(iam_client, role_name)
    except ClientError:
        return False
    
    # Detach managed policies
    print("\n2. Detaching managed policies...")
    try:
        managed_count = detach_managed_policies(iam_client, role_name)
    except ClientError:
        return False
    
    # Delete role
    print("\n3. Deleting role...")
    success = delete_role(iam_client, role_name)
    
    if success:
        print("\n" + "=" * 80)
        print("SUCCESS! IAM role deleted successfully")
        print("=" * 80)
        print(f"\nDeleted:")
        print(f"  - {inline_count} inline policies")
        print(f"  - {managed_count} managed policies")
        print(f"  - Role: {role_name}")
        print("\nThe role has been completely removed from your AWS account.")
    
    return success


def main():
    parser = argparse.ArgumentParser(
        description="Clean up IAM role for SageMaker LLM finetuning pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Delete role with confirmation
  python cleanup_role.py --role-name SageMakerFinetuningRole
  
  # Delete role by ARN
  python cleanup_role.py --role-arn arn:aws:iam::123456789012:role/MyRole
  
  # Delete without confirmation (use with caution!)
  python cleanup_role.py --role-name MyRole --force
  
  # Use specific AWS profile
  python cleanup_role.py --role-name MyRole --profile production
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--role-name",
        help="Name of the IAM role to delete"
    )
    group.add_argument(
        "--role-arn",
        help="ARN of the IAM role to delete"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt (use with caution!)"
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
    
    # Extract role name from ARN if provided
    if args.role_arn:
        role_name = args.role_arn.split("/")[-1]
    else:
        role_name = args.role_name
    
    # Create AWS client
    session_kwargs = {"region_name": args.region}
    if args.profile:
        session_kwargs["profile_name"] = args.profile
    
    try:
        session = boto3.Session(**session_kwargs)
        iam_client = session.client("iam")
    except (ClientError, BotoCoreError) as e:
        print(f"Error: Failed to create AWS client: {e}")
        print("\nEnsure AWS credentials are configured:")
        print("  aws configure")
        sys.exit(1)
    
    # Clean up role
    try:
        success = cleanup_role(
            iam_client=iam_client,
            role_name=role_name,
            force=args.force
        )
        
        sys.exit(0 if success else 1)
        
    except ClientError as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
