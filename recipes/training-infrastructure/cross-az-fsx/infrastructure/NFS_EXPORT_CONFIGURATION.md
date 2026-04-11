# FSx NetApp ONTAP NFS Export Configuration Guide

## Overview

This guide provides instructions for configuring NFS export policies on the FSx NetApp ONTAP volume to allow SageMaker Training Jobs to access genomic training data with appropriate permissions.

## Background

FSx NetApp ONTAP uses export policies to control NFS client access to volumes. An export policy consists of one or more rules that specify:
- Which clients can access the volume (by IP address, CIDR block, or hostname)
- What access permissions they have (read-only, read-write, superuser)
- Which NFS protocols are allowed (NFSv3, NFSv4)

## Prerequisites

- FSx NetApp ONTAP file system deployed (Task 1.4 completed)
- Storage Virtual Machine (SVM) created
- Volume created with junction path `/genomics`
- VPC and security groups configured for NFS access (Task 1.2 completed)
- AWS CLI configured with appropriate credentials

## Configuration Requirements

For the cross-AZ validation system, the NFS export policy must:

1. **Allow access from SageMaker Training Jobs** in us-west-2b subnet
2. **Provide read-write permissions** for data preparation and training
3. **Support both NFSv3 and NFSv4** protocols
4. **Enable superuser access** for file operations
5. **Restrict access to VPC CIDR** for security

## Configuration Methods

### Method 1: Using the Configuration Script (Recommended)

The `configure_nfs_export.py` script generates ONTAP CLI commands for configuring the export policy.

#### Step 1: Retrieve SVM ID

```bash
# Get SVM ID from CloudFormation stack outputs
SVM_ID=$(aws cloudformation describe-stacks \
  --stack-name CrossAzFsxSageMakerFsx \
  --query 'Stacks[0].Outputs[?OutputKey==`StorageVirtualMachineId`].OutputValue' \
  --output text \
  --region us-west-2)

echo "SVM ID: $SVM_ID"
```

#### Step 2: Get VPC ID

```bash
# Get VPC ID from network stack
VPC_ID=$(aws cloudformation describe-stacks \
  --stack-name CrossAzFsxSageMakerNetwork \
  --query 'Stacks[0].Outputs[?OutputKey==`VpcId`].OutputValue' \
  --output text \
  --region us-west-2)

echo "VPC ID: $VPC_ID"
```

#### Step 3: Generate Export Policy Commands

```bash
cd infrastructure

# Generate ONTAP CLI commands
python configure_nfs_export.py \
  --svm-id $SVM_ID \
  --vpc-id $VPC_ID \
  --volume-name genomics-training-data \
  --policy-name sagemaker-access \
  --region us-west-2 \
  --output nfs_export_commands.sh
```

This will generate:
- `nfs_export_commands.sh`: ONTAP CLI commands to execute
- `nfs_export_commands.json`: Configuration metadata

#### Step 4: Access FSx NetApp ONTAP CLI

FSx NetApp ONTAP provides a management endpoint for CLI access. You can access it via:

**Option A: AWS Systems Manager Session Manager**

```bash
# Get the file system ID
FS_ID=$(aws cloudformation describe-stacks \
  --stack-name CrossAzFsxSageMakerFsx \
  --query 'Stacks[0].Outputs[?OutputKey==`FileSystemId`].OutputValue' \
  --output text \
  --region us-west-2)

# Get the management endpoint
aws fsx describe-file-systems \
  --file-system-ids $FS_ID \
  --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.DNSName' \
  --output text \
  --region us-west-2
```

**Option B: SSH Access (if configured)**

```bash
# SSH to FSx management endpoint
ssh fsxadmin@<MANAGEMENT-ENDPOINT>
```

#### Step 5: Execute ONTAP CLI Commands

Once connected to the ONTAP CLI, execute the commands from `nfs_export_commands.sh`:

```bash
# Create export policy
vserver export-policy create -vserver svm-genomics -policyname sagemaker-access

# Add export rule allowing access from VPC CIDR
vserver export-policy rule create -vserver svm-genomics -policyname sagemaker-access \
  -clientmatch 10.0.0.0/16 \
  -rorule sys -rwrule sys -superuser sys \
  -protocol nfs3,nfs4

# Apply export policy to volume
volume modify -vserver svm-genomics -volume genomics_training_data -policy sagemaker-access

# Verify export policy
vserver export-policy show -vserver svm-genomics -policyname sagemaker-access
vserver export-policy rule show -vserver svm-genomics -policyname sagemaker-access
```

### Method 2: Using AWS FSx Console

1. Navigate to AWS FSx Console
2. Select your FSx NetApp ONTAP file system
3. Go to "Storage virtual machines" tab
4. Select the SVM (svm-genomics)
5. Go to "Volumes" tab
6. Select the volume (genomics-training-data)
7. Click "Actions" → "Update volume"
8. Configure export policy settings
9. Save changes

### Method 3: Using ONTAP REST API

```python
import requests
import json

# FSx NetApp ONTAP REST API endpoint
management_endpoint = "<MANAGEMENT-ENDPOINT>"
api_url = f"https://{management_endpoint}/api"

# Authentication
auth = ("fsxadmin", "<PASSWORD>")

# Create export policy
export_policy_data = {
    "name": "sagemaker-access",
    "svm": {"name": "svm-genomics"}
}

response = requests.post(
    f"{api_url}/protocols/nfs/export-policies",
    auth=auth,
    json=export_policy_data,
    verify=False
)

# Add export rule
export_rule_data = {
    "clients": [{"match": "10.0.0.0/16"}],
    "ro_rule": ["sys"],
    "rw_rule": ["sys"],
    "superuser": ["sys"],
    "protocols": ["nfs3", "nfs4"]
}

policy_id = response.json()["uuid"]
response = requests.post(
    f"{api_url}/protocols/nfs/export-policies/{policy_id}/rules",
    auth=auth,
    json=export_rule_data,
    verify=False
)
```

## Export Policy Configuration Details

### Policy Name
- **Name**: `sagemaker-access`
- **Purpose**: Allow SageMaker Training Jobs to access genomics training data

### Export Rules

| Parameter | Value | Description |
|-----------|-------|-------------|
| Client Match | `10.0.0.0/16` | VPC CIDR block (adjust based on your VPC) |
| RO Rule | `sys` | Read-only access using AUTH_SYS (standard NFS authentication) |
| RW Rule | `sys` | Read-write access using AUTH_SYS |
| Superuser | `sys` | Superuser access using AUTH_SYS |
| Protocols | `nfs3,nfs4` | Support both NFSv3 and NFSv4 |
| Anonymous User | `65534` | Map anonymous users to nobody (UID 65534) |

### Security Considerations

1. **Client Match Pattern**
   - Use VPC CIDR (e.g., `10.0.0.0/16`) to restrict access to VPC resources
   - For tighter security, use specific subnet CIDR (e.g., `10.0.2.0/24` for us-west-2b)
   - Avoid using `0.0.0.0/0` in production

2. **Authentication**
   - `sys` uses standard NFS AUTH_SYS (UID/GID-based authentication)
   - For enhanced security, consider using Kerberos (`krb5`, `krb5i`, `krb5p`)

3. **Permissions**
   - Read-write access is required for data preparation and training
   - Superuser access allows file ownership changes and system operations

## Verification

### Verify Export Policy Configuration

```bash
# Connect to ONTAP CLI
ssh fsxadmin@<MANAGEMENT-ENDPOINT>

# Show export policy
vserver export-policy show -vserver svm-genomics -policyname sagemaker-access

# Show export rules
vserver export-policy rule show -vserver svm-genomics -policyname sagemaker-access

# Verify volume is using the policy
volume show -vserver svm-genomics -volume genomics_training_data -fields policy
```

Expected output:
```
Policy Name: sagemaker-access
Rule Index: 1
Client Match: 10.0.0.0/16
RO Rule: sys
RW Rule: sys
Superuser: sys
Protocols: nfs3,nfs4
```

### Test NFS Mount from SageMaker

Create a test SageMaker Training Job or EC2 instance in us-west-2b and test the mount:

```bash
# Get SVM DNS name
SVM_DNS=$(aws fsx describe-storage-virtual-machines \
  --storage-virtual-machine-ids $SVM_ID \
  --query 'StorageVirtualMachines[0].Endpoints.Nfs.DNSName' \
  --output text \
  --region us-west-2)

# Create mount point
sudo mkdir -p /mnt/fsx

# Mount the volume
sudo mount -t nfs -o nfsvers=4.1 $SVM_DNS:/genomics /mnt/fsx

# Verify mount
df -h /mnt/fsx
ls -la /mnt/fsx

# Test write access
echo "Test write" | sudo tee /mnt/fsx/test.txt

# Test read access
cat /mnt/fsx/test.txt

# Clean up
sudo rm /mnt/fsx/test.txt
sudo umount /mnt/fsx
```

### Verify Cross-AZ Access

From a SageMaker Training Job in us-west-2b:

```python
import os
import subprocess

# Mount FSx volume
svm_dns = "<SVM-DNS-NAME>"
mount_point = "/mnt/fsx"

os.makedirs(mount_point, exist_ok=True)
subprocess.run([
    "mount", "-t", "nfs", "-o", "nfsvers=4.1",
    f"{svm_dns}:/genomics", mount_point
], check=True)

# Test write access
test_file = os.path.join(mount_point, "cross_az_test.txt")
with open(test_file, "w") as f:
    f.write("Cross-AZ write test successful\n")

# Test read access
with open(test_file, "r") as f:
    content = f.read()
    print(f"Read from FSx: {content}")

# Verify permissions
stat_info = os.stat(test_file)
print(f"File permissions: {oct(stat_info.st_mode)}")
print(f"File owner UID: {stat_info.st_uid}")
print(f"File owner GID: {stat_info.st_gid}")

# Clean up
os.remove(test_file)
print("✅ Cross-AZ NFS access verified successfully!")
```

## Troubleshooting

### Issue: Mount fails with "Permission denied"

**Cause**: Export policy not configured or client not in allowed list

**Solution**:
1. Verify export policy exists: `vserver export-policy show`
2. Check export rules: `vserver export-policy rule show`
3. Verify client IP is in allowed CIDR range
4. Check security group allows NFS traffic (port 2049)

### Issue: Mount fails with "Connection refused"

**Cause**: Network connectivity issue or security group misconfiguration

**Solution**:
1. Verify security group allows NFS traffic from SageMaker subnet
2. Check VPC routing tables
3. Verify SVM NFS endpoint is accessible: `ping <SVM-DNS-NAME>`
4. Check VPC Flow Logs for blocked traffic

### Issue: Read-only file system

**Cause**: Export policy only allows read-only access

**Solution**:
1. Verify export rule has `rwrule sys`: `vserver export-policy rule show`
2. Update export rule if needed:
   ```bash
   vserver export-policy rule modify -vserver svm-genomics \
     -policyname sagemaker-access -ruleindex 1 -rwrule sys
   ```

### Issue: Cannot create files as root

**Cause**: Superuser access not enabled

**Solution**:
1. Verify export rule has `superuser sys`: `vserver export-policy rule show`
2. Update export rule if needed:
   ```bash
   vserver export-policy rule modify -vserver svm-genomics \
     -policyname sagemaker-access -ruleindex 1 -superuser sys
   ```

## Best Practices

1. **Use specific CIDR blocks**: Restrict access to specific subnets rather than entire VPC
2. **Enable encryption in transit**: Use NFSv4.1 with Kerberos for encrypted data transfer
3. **Monitor access**: Enable CloudWatch logging for NFS access patterns
4. **Regular audits**: Review export policies regularly to ensure least privilege
5. **Document changes**: Keep track of export policy modifications
6. **Test before production**: Validate export policies in test environment first

## Integration with SageMaker Training Jobs

### Mount Configuration in Training Script

```python
import os
import subprocess
import logging

logger = logging.getLogger(__name__)

def mount_fsx_volume(svm_dns: str, junction_path: str, mount_point: str) -> bool:
    """
    Mount FSx NetApp ONTAP volume in SageMaker Training Job
    
    Args:
        svm_dns: SVM NFS endpoint DNS name
        junction_path: Volume junction path (e.g., /genomics)
        mount_point: Local mount point (e.g., /mnt/fsx)
    
    Returns:
        True if mount successful, False otherwise
    """
    try:
        # Create mount point
        os.makedirs(mount_point, exist_ok=True)
        
        # Mount with NFSv4.1
        mount_cmd = [
            "mount", "-t", "nfs", "-o", "nfsvers=4.1,rsize=1048576,wsize=1048576",
            f"{svm_dns}:{junction_path}", mount_point
        ]
        
        logger.info(f"Mounting FSx volume: {' '.join(mount_cmd)}")
        subprocess.run(mount_cmd, check=True, capture_output=True, text=True)
        
        # Verify mount
        if not os.path.ismount(mount_point):
            logger.error(f"Mount point {mount_point} is not mounted")
            return False
        
        logger.info(f"✅ FSx volume mounted successfully at {mount_point}")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to mount FSx volume: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error mounting FSx volume: {e}")
        return False
```

### SageMaker Training Job Configuration

```python
from sagemaker.estimator import Estimator

# FSx configuration
fsx_config = {
    "svm_dns": "<SVM-DNS-NAME>",
    "junction_path": "/genomics",
    "mount_point": "/mnt/fsx"
}

# Create estimator with FSx mount
estimator = Estimator(
    image_uri="<BIONEMO-CONTAINER-URI>",
    role="<SAGEMAKER-ROLE-ARN>",
    instance_count=1,
    instance_type="ml.p5.48xlarge",
    subnets=["<SAGEMAKER-SUBNET-ID>"],  # us-west-2b subnet
    security_group_ids=["<SAGEMAKER-SECURITY-GROUP-ID>"],
    environment={
        "FSX_SVM_DNS": fsx_config["svm_dns"],
        "FSX_JUNCTION_PATH": fsx_config["junction_path"],
        "FSX_MOUNT_POINT": fsx_config["mount_point"]
    }
)
```

## Next Steps

After configuring the NFS export policy:

1. ✅ Task 1.5: Configure FSx NFS export with appropriate permissions (COMPLETED)
2. ⏭️ Task 1.6: Enable CloudWatch monitoring for FSx volume
3. ⏭️ Task 1.7: Verify P5 instance availability in us-west-2b
4. ⏭️ Phase 2: Data Preparation (prepare hg38 datasets)
5. ⏭️ Phase 3: Core Components Implementation (FSxMountManager, etc.)

## References

- [FSx NetApp ONTAP User Guide](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/)
- [ONTAP Export Policy Documentation](https://docs.netapp.com/us-en/ontap/nfs-admin/index.html)
- [SageMaker VPC Configuration](https://docs.aws.amazon.com/sagemaker/latest/dg/train-vpc.html)
- [NFS Best Practices](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html)
