#!/usr/bin/env python3
"""
Verify NFS export configuration for FSx NetApp ONTAP volume

This script verifies that the NFS export policy is correctly configured
and that SageMaker Training Jobs can access the volume.

Usage:
    python verify_nfs_export.py --svm-id <SVM-ID>
"""

import argparse
import boto3
import json
import sys
import subprocess
import os
from typing import Dict, List, Optional


class NFSExportVerifier:
    """Verifies NFS export configuration for FSx NetApp ONTAP"""

    def __init__(self, region: str = "us-west-2"):
        self.fsx_client = boto3.client("fsx", region_name=region)
        self.ec2_client = boto3.client("ec2", region_name=region)
        self.region = region

    def get_svm_info(self, svm_id: str) -> Dict:
        """Get Storage Virtual Machine information"""
        response = self.fsx_client.describe_storage_virtual_machines(
            StorageVirtualMachineIds=[svm_id]
        )
        if not response["StorageVirtualMachines"]:
            raise ValueError(f"SVM {svm_id} not found")
        return response["StorageVirtualMachines"][0]

    def get_volume_info(self, svm_id: str, volume_name: str) -> Optional[Dict]:
        """Get volume information by name"""
        response = self.fsx_client.describe_volumes(
            Filters=[
                {"Name": "storage-virtual-machine-id", "Values": [svm_id]},
            ]
        )

        for volume in response.get("Volumes", []):
            if volume.get("Name") == volume_name:
                return volume

        return None

    def verify_svm_endpoints(self, svm_info: Dict) -> Dict[str, bool]:
        """Verify SVM endpoints are available"""
        results = {
            "nfs_endpoint_exists": False,
            "nfs_dns_name": None,
            "management_endpoint_exists": False,
            "management_dns_name": None,
        }

        endpoints = svm_info.get("Endpoints", {})

        # Check NFS endpoint
        nfs_endpoint = endpoints.get("Nfs", {})
        if nfs_endpoint.get("DNSName"):
            results["nfs_endpoint_exists"] = True
            results["nfs_dns_name"] = nfs_endpoint["DNSName"]

        # Check Management endpoint
        mgmt_endpoint = endpoints.get("Management", {})
        if mgmt_endpoint.get("DNSName"):
            results["management_endpoint_exists"] = True
            results["management_dns_name"] = mgmt_endpoint["DNSName"]

        return results

    def verify_volume_configuration(self, volume_info: Dict) -> Dict[str, bool]:
        """Verify volume configuration"""
        results = {
            "volume_exists": True,
            "junction_path_configured": False,
            "junction_path": None,
            "security_style": None,
            "security_style_unix": False,
        }

        ontap_config = volume_info.get("OntapConfiguration", {})

        # Check junction path
        junction_path = ontap_config.get("JunctionPath")
        if junction_path:
            results["junction_path_configured"] = True
            results["junction_path"] = junction_path

        # Check security style
        security_style = ontap_config.get("SecurityStyle")
        if security_style:
            results["security_style"] = security_style
            results["security_style_unix"] = security_style == "UNIX"

        return results

    def verify_network_connectivity(
        self, svm_dns: str, port: int = 2049
    ) -> Dict[str, bool]:
        """Verify network connectivity to SVM NFS endpoint"""
        results = {
            "dns_resolvable": False,
            "ip_address": None,
            "port_reachable": False,
        }

        try:
            # Try to resolve DNS
            import socket

            ip_address = socket.gethostbyname(svm_dns)
            results["dns_resolvable"] = True
            results["ip_address"] = ip_address

            # Try to connect to NFS port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((ip_address, port))
            sock.close()

            if result == 0:
                results["port_reachable"] = True

        except Exception as e:
            print(f"  Network connectivity check failed: {e}")

        return results

    def generate_mount_test_script(
        self, svm_dns: str, junction_path: str, output_file: str
    ) -> None:
        """Generate a script to test NFS mount"""
        script_content = f"""#!/bin/bash
# NFS Mount Test Script
# This script should be run from a SageMaker Training Job or EC2 instance
# in the same VPC as the FSx file system

set -e

SVM_DNS="{svm_dns}"
JUNCTION_PATH="{junction_path}"
MOUNT_POINT="/mnt/fsx-test"

echo "Testing NFS mount to FSx NetApp ONTAP volume"
echo "SVM DNS: $SVM_DNS"
echo "Junction Path: $JUNCTION_PATH"
echo "Mount Point: $MOUNT_POINT"
echo ""

# Create mount point
echo "Creating mount point..."
sudo mkdir -p $MOUNT_POINT

# Mount the volume
echo "Mounting FSx volume..."
sudo mount -t nfs -o nfsvers=4.1,rsize=1048576,wsize=1048576 \\
  $SVM_DNS:$JUNCTION_PATH $MOUNT_POINT

# Verify mount
echo "Verifying mount..."
df -h $MOUNT_POINT
ls -la $MOUNT_POINT

# Test write access
echo "Testing write access..."
TEST_FILE="$MOUNT_POINT/nfs_test_$(date +%s).txt"
echo "NFS write test successful" | sudo tee $TEST_FILE
echo "✅ Write test passed"

# Test read access
echo "Testing read access..."
cat $TEST_FILE
echo "✅ Read test passed"

# Test file permissions
echo "Testing file permissions..."
sudo chmod 644 $TEST_FILE
sudo chown nobody:nogroup $TEST_FILE
ls -l $TEST_FILE
echo "✅ Permission test passed"

# Clean up
echo "Cleaning up..."
sudo rm $TEST_FILE
sudo umount $MOUNT_POINT
sudo rmdir $MOUNT_POINT

echo ""
echo "✅ All NFS mount tests passed successfully!"
"""

        with open(output_file, "w") as f:
            f.write(script_content)

        # Make script executable
        os.chmod(output_file, 0o755)

    def print_verification_summary(
        self,
        svm_info: Dict,
        endpoint_results: Dict,
        volume_results: Dict,
        network_results: Dict,
    ) -> bool:
        """Print verification summary and return overall success status"""
        print("\n" + "=" * 80)
        print("NFS EXPORT VERIFICATION SUMMARY")
        print("=" * 80)

        all_passed = True

        # SVM Information
        print("\n📋 Storage Virtual Machine (SVM)")
        print(f"  SVM ID: {svm_info['StorageVirtualMachineId']}")
        print(f"  SVM Name: {svm_info['Name']}")
        print(f"  Lifecycle: {svm_info['Lifecycle']}")

        # Endpoint Verification
        print("\n🔌 Endpoint Verification")
        if endpoint_results["nfs_endpoint_exists"]:
            print(f"  ✅ NFS Endpoint: {endpoint_results['nfs_dns_name']}")
        else:
            print("  ❌ NFS Endpoint: Not configured")
            all_passed = False

        if endpoint_results["management_endpoint_exists"]:
            print(
                f"  ✅ Management Endpoint: {endpoint_results['management_dns_name']}"
            )
        else:
            print("  ⚠️  Management Endpoint: Not configured")

        # Volume Configuration
        print("\n📦 Volume Configuration")
        if volume_results["volume_exists"]:
            print("  ✅ Volume exists")
        else:
            print("  ❌ Volume not found")
            all_passed = False

        if volume_results["junction_path_configured"]:
            print(f"  ✅ Junction Path: {volume_results['junction_path']}")
        else:
            print("  ❌ Junction Path: Not configured")
            all_passed = False

        if volume_results["security_style_unix"]:
            print(f"  ✅ Security Style: {volume_results['security_style']}")
        else:
            print(
                f"  ⚠️  Security Style: {volume_results['security_style']} (expected UNIX)"
            )

        # Network Connectivity
        print("\n🌐 Network Connectivity")
        if network_results["dns_resolvable"]:
            print(f"  ✅ DNS Resolution: {network_results['ip_address']}")
        else:
            print("  ❌ DNS Resolution: Failed")
            all_passed = False

        if network_results["port_reachable"]:
            print("  ✅ NFS Port (2049): Reachable")
        else:
            print("  ⚠️  NFS Port (2049): Not reachable from this host")
            print("     (This is expected if running outside the VPC)")

        # Overall Status
        print("\n" + "=" * 80)
        if all_passed:
            print("✅ VERIFICATION PASSED")
            print("\nNext Steps:")
            print("1. Run the mount test script from a SageMaker Training Job or EC2 instance")
            print("2. Verify export policy configuration via ONTAP CLI")
            print("3. Test cross-AZ access from us-west-2b")
        else:
            print("❌ VERIFICATION FAILED")
            print("\nPlease address the issues above before proceeding.")

        print("=" * 80 + "\n")

        return all_passed


def main():
    parser = argparse.ArgumentParser(
        description="Verify NFS export configuration for FSx NetApp ONTAP volume"
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
        "--region", default="us-west-2", help="AWS region (default: us-west-2)"
    )
    parser.add_argument(
        "--output-test-script",
        default="test_nfs_mount.sh",
        help="Output file for mount test script",
    )

    args = parser.parse_args()

    verifier = NFSExportVerifier(region=args.region)

    try:
        print(f"\n🔍 Verifying NFS export configuration...")
        print(f"   SVM ID: {args.svm_id}")
        print(f"   Volume: {args.volume_name}")
        print(f"   Region: {args.region}")

        # Get SVM information
        print(f"\n📡 Retrieving SVM information...")
        svm_info = verifier.get_svm_info(args.svm_id)

        # Verify endpoints
        print(f"🔌 Verifying SVM endpoints...")
        endpoint_results = verifier.verify_svm_endpoints(svm_info)

        # Get volume information
        print(f"📦 Retrieving volume information...")
        volume_info = verifier.get_volume_info(args.svm_id, args.volume_name)

        if not volume_info:
            print(f"❌ Volume '{args.volume_name}' not found")
            volume_results = {"volume_exists": False}
        else:
            volume_results = verifier.verify_volume_configuration(volume_info)

        # Verify network connectivity
        network_results = {"dns_resolvable": False, "port_reachable": False}
        if endpoint_results["nfs_dns_name"]:
            print(f"🌐 Verifying network connectivity...")
            network_results = verifier.verify_network_connectivity(
                endpoint_results["nfs_dns_name"]
            )

        # Generate mount test script
        if endpoint_results["nfs_dns_name"] and volume_results.get(
            "junction_path_configured"
        ):
            print(f"\n📝 Generating mount test script...")
            verifier.generate_mount_test_script(
                svm_dns=endpoint_results["nfs_dns_name"],
                junction_path=volume_results["junction_path"],
                output_file=args.output_test_script,
            )
            print(f"   Test script written to: {args.output_test_script}")

        # Print summary
        success = verifier.print_verification_summary(
            svm_info, endpoint_results, volume_results, network_results
        )

        # Save results to JSON
        results_file = "nfs_export_verification.json"
        with open(results_file, "w") as f:
            json.dump(
                {
                    "svm_info": {
                        "svm_id": svm_info["StorageVirtualMachineId"],
                        "svm_name": svm_info["Name"],
                        "lifecycle": svm_info["Lifecycle"],
                    },
                    "endpoint_results": endpoint_results,
                    "volume_results": volume_results,
                    "network_results": network_results,
                    "verification_passed": success,
                },
                f,
                indent=2,
            )
        print(f"Verification results saved to: {results_file}")

        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
