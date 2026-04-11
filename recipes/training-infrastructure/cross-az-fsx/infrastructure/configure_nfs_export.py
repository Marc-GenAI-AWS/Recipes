#!/usr/bin/env python3
"""
Configure NFS export policy for FSx NetApp ONTAP volume

This script configures the NFS export policy for the genomics training data volume
to allow SageMaker Training Jobs to access data with appropriate permissions.

Usage:
    python configure_nfs_export.py --svm-id <SVM-ID> --volume-name genomics-training-data
"""

import argparse
import boto3
import json
import sys
from typing import Dict, List, Optional


class NFSExportConfigurator:
    """Configures NFS export policies for FSx NetApp ONTAP volumes"""

    def __init__(self, region: str = "us-west-2"):
        self.fsx_client = boto3.client("fsx", region_name=region)
        self.ec2_client = boto3.client("ec2", region_name=region)

    def get_sagemaker_subnet_cidr(self, subnet_id: str) -> str:
        """Get CIDR block for SageMaker subnet"""
        response = self.ec2_client.describe_subnets(SubnetIds=[subnet_id])
        return response["Subnets"][0]["CidrBlock"]

    def get_vpc_cidr(self, vpc_id: str) -> str:
        """Get CIDR block for VPC"""
        response = self.ec2_client.describe_vpcs(VpcIds=[vpc_id])
        return response["Vpcs"][0]["CidrBlock"]

    def create_export_policy(
        self,
        svm_id: str,
        policy_name: str,
        client_match: str,
        ro_rule: List[str] = ["sys"],
        rw_rule: List[str] = ["sys"],
        super_user: List[str] = ["sys"],
    ) -> Dict:
        """
        Create NFS export policy for FSx volume

        Args:
            svm_id: Storage Virtual Machine ID
            policy_name: Name for the export policy
            client_match: Client match pattern (IP, CIDR, or hostname)
            ro_rule: Read-only access rules (default: sys for AUTH_SYS)
            rw_rule: Read-write access rules (default: sys for AUTH_SYS)
            super_user: Superuser access rules (default: sys for AUTH_SYS)

        Returns:
            Response from FSx API
        """
        print(f"Creating export policy '{policy_name}' for SVM {svm_id}")
        print(f"  Client match: {client_match}")
        print(f"  RO rule: {ro_rule}")
        print(f"  RW rule: {rw_rule}")
        print(f"  Superuser: {super_user}")

        # Note: FSx NetApp ONTAP export policies are managed through the ONTAP CLI
        # or REST API, not through the AWS FSx API. This script provides the
        # configuration that should be applied.

        export_policy_config = {
            "policy_name": policy_name,
            "rules": [
                {
                    "client_match": client_match,
                    "ro_rule": ro_rule,
                    "rw_rule": rw_rule,
                    "super_user": super_user,
                    "protocol": ["nfs3", "nfs4"],
                    "anonymous_user": "65534",  # nobody user
                }
            ],
        }

        return export_policy_config

    def get_volume_info(self, volume_id: str) -> Dict:
        """Get volume information"""
        response = self.fsx_client.describe_volumes(VolumeIds=[volume_id])
        if not response["Volumes"]:
            raise ValueError(f"Volume {volume_id} not found")
        return response["Volumes"][0]

    def get_svm_info(self, svm_id: str) -> Dict:
        """Get Storage Virtual Machine information"""
        response = self.fsx_client.describe_storage_virtual_machines(
            StorageVirtualMachineIds=[svm_id]
        )
        if not response["StorageVirtualMachines"]:
            raise ValueError(f"SVM {svm_id} not found")
        return response["StorageVirtualMachines"][0]

    def generate_ontap_commands(
        self, svm_name: str, volume_name: str, policy_name: str, client_match: str
    ) -> List[str]:
        """
        Generate ONTAP CLI commands to configure export policy

        Args:
            svm_name: SVM name
            volume_name: Volume name
            policy_name: Export policy name
            client_match: Client match pattern

        Returns:
            List of ONTAP CLI commands
        """
        commands = [
            f"# Create export policy",
            f"vserver export-policy create -vserver {svm_name} -policyname {policy_name}",
            f"",
            f"# Add export rule allowing access from SageMaker subnet",
            f"vserver export-policy rule create -vserver {svm_name} -policyname {policy_name} \\",
            f"  -clientmatch {client_match} \\",
            f"  -rorule sys -rwrule sys -superuser sys \\",
            f"  -protocol nfs3,nfs4",
            f"",
            f"# Apply export policy to volume",
            f"volume modify -vserver {svm_name} -volume {volume_name} -policy {policy_name}",
            f"",
            f"# Verify export policy",
            f"vserver export-policy show -vserver {svm_name} -policyname {policy_name}",
            f"vserver export-policy rule show -vserver {svm_name} -policyname {policy_name}",
        ]
        return commands


def main():
    parser = argparse.ArgumentParser(
        description="Configure NFS export policy for FSx NetApp ONTAP volume"
    )
    parser.add_argument(
        "--svm-id", required=True, help="Storage Virtual Machine ID"
    )
    parser.add_argument(
        "--volume-name",
        default="genomics-training-data",
        help="Volume name (default: genomics-training-data)",
    )
    parser.add_argument(
        "--policy-name",
        default="sagemaker-access",
        help="Export policy name (default: sagemaker-access)",
    )
    parser.add_argument(
        "--vpc-id", help="VPC ID (optional, will use VPC CIDR for client match)"
    )
    parser.add_argument(
        "--client-match",
        help="Client match pattern (IP/CIDR). If not provided, will use VPC CIDR",
    )
    parser.add_argument(
        "--region", default="us-west-2", help="AWS region (default: us-west-2)"
    )
    parser.add_argument(
        "--output",
        default="nfs_export_commands.sh",
        help="Output file for ONTAP commands",
    )

    args = parser.parse_args()

    configurator = NFSExportConfigurator(region=args.region)

    try:
        # Get SVM information
        print(f"\nRetrieving SVM information...")
        svm_info = configurator.get_svm_info(args.svm_id)
        svm_name = svm_info["Name"]
        file_system_id = svm_info["FileSystemId"]

        print(f"  SVM Name: {svm_name}")
        print(f"  File System ID: {file_system_id}")

        # Determine client match pattern
        if args.client_match:
            client_match = args.client_match
        elif args.vpc_id:
            print(f"\nRetrieving VPC CIDR...")
            client_match = configurator.get_vpc_cidr(args.vpc_id)
            print(f"  VPC CIDR: {client_match}")
        else:
            # Default to allow all (should be restricted in production)
            client_match = "0.0.0.0/0"
            print(
                f"\nWARNING: No client match specified, using {client_match} (allows all)"
            )
            print("  For production, specify --vpc-id or --client-match")

        # Create export policy configuration
        print(f"\nGenerating export policy configuration...")
        export_config = configurator.create_export_policy(
            svm_id=args.svm_id,
            policy_name=args.policy_name,
            client_match=client_match,
            ro_rule=["sys"],
            rw_rule=["sys"],
            super_user=["sys"],
        )

        # Generate ONTAP CLI commands
        print(f"\nGenerating ONTAP CLI commands...")
        commands = configurator.generate_ontap_commands(
            svm_name=svm_name,
            volume_name=args.volume_name,
            policy_name=args.policy_name,
            client_match=client_match,
        )

        # Write commands to file
        with open(args.output, "w") as f:
            f.write("#!/bin/bash\n")
            f.write("# NFS Export Policy Configuration Commands\n")
            f.write(f"# Generated for SVM: {svm_name}\n")
            f.write(f"# Volume: {args.volume_name}\n")
            f.write(f"# Policy: {args.policy_name}\n")
            f.write(f"# Client Match: {client_match}\n")
            f.write("\n")
            f.write("# These commands should be executed via FSx NetApp ONTAP CLI\n")
            f.write(
                "# Access the CLI using AWS Systems Manager Session Manager or SSH\n"
            )
            f.write("\n")
            for cmd in commands:
                f.write(cmd + "\n")

        print(f"\n✅ Export policy configuration generated successfully!")
        print(f"   Commands written to: {args.output}")
        print(f"\nNext steps:")
        print(f"1. Access FSx NetApp ONTAP CLI via AWS Systems Manager")
        print(f"2. Execute the commands in {args.output}")
        print(f"3. Verify export policy is applied to volume")
        print(f"\nExport Policy Summary:")
        print(f"  Policy Name: {args.policy_name}")
        print(f"  Volume: {args.volume_name}")
        print(f"  Client Match: {client_match}")
        print(f"  Permissions: Read/Write with superuser access")
        print(f"  Protocols: NFSv3, NFSv4")

        # Save configuration as JSON
        config_file = args.output.replace(".sh", ".json")
        with open(config_file, "w") as f:
            json.dump(
                {
                    "svm_id": args.svm_id,
                    "svm_name": svm_name,
                    "volume_name": args.volume_name,
                    "policy_name": args.policy_name,
                    "client_match": client_match,
                    "export_config": export_config,
                },
                f,
                indent=2,
            )
        print(f"  Configuration saved to: {config_file}")

    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
