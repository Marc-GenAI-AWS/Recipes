# FSx NetApp ONTAP Deployment Guide

## Overview

This guide provides instructions for deploying and using the FSx NetApp ONTAP file system for cross-AZ validation testing.

## Prerequisites

- AWS CDK CLI installed (`npm install -g aws-cdk`)
- AWS credentials configured
- Python dependencies installed (`pip install -r requirements.txt`)
- Network stack and IAM stack already deployed

## Deployment Steps

### 1. Deploy the FSx Stack

```bash
cd infrastructure
npx cdk deploy CrossAzFsxSageMakerFsx
```

The deployment will create:
- FSx NetApp ONTAP file system in us-west-2a
- Storage Virtual Machine (SVM) for NFS access
- Volume with 1 TiB capacity at junction path `/genomics`

### 2. Retrieve FSx Connection Information

After deployment, get the SVM DNS name:

```bash
# Get the SVM ID from stack outputs
SVM_ID=$(aws cloudformation describe-stacks \
  --stack-name CrossAzFsxSageMakerFsx \
  --query 'Stacks[0].Outputs[?OutputKey==`StorageVirtualMachineId`].OutputValue' \
  --output text)

# Get the SVM DNS name
aws fsx describe-storage-virtual-machines \
  --storage-virtual-machine-ids $SVM_ID \
  --query 'StorageVirtualMachines[0].Endpoints.Nfs.DNSName' \
  --output text
```

Save this DNS name - you'll need it for mounting.

### 3. Mount the FSx Volume

From a SageMaker Training Job or EC2 instance in the VPC:

```bash
# Create mount point
sudo mkdir -p /mnt/fsx

# Mount the FSx volume
sudo mount -t nfs <SVM-DNS-NAME>:/genomics /mnt/fsx

# Verify mount
df -h /mnt/fsx
ls -la /mnt/fsx
```

### 4. Test Cross-AZ Access

From a SageMaker Training Job in us-west-2b:

```python
import os
import time

# Verify mount is accessible
mount_point = "/mnt/fsx"
assert os.path.exists(mount_point), f"Mount point {mount_point} does not exist"

# Test write access
test_file = os.path.join(mount_point, "test.txt")
with open(test_file, "w") as f:
    f.write("Cross-AZ test successful\n")

# Test read access
with open(test_file, "r") as f:
    content = f.read()
    print(f"Read from FSx: {content}")

# Clean up
os.remove(test_file)
print("Cross-AZ FSx access validated successfully!")
```

## Configuration Details

### File System Specifications

- **Type**: FSx NetApp ONTAP
- **Deployment**: Single-AZ (us-west-2a)
- **Storage Capacity**: 1024 GiB (1 TiB)
- **Throughput**: 128 MBps
- **Availability Zone**: us-west-2a

### Volume Specifications

- **Name**: genomics-training-data
- **Junction Path**: /genomics
- **Size**: 1 TiB
- **Security Style**: UNIX
- **Storage Efficiency**: Enabled
- **Tiering Policy**: AUTO (31-day cooling period)

### Network Configuration

- **VPC**: cross-az-fsx-sagemaker-vpc (10.0.0.0/16)
- **Subnet**: us-west-2a public subnet
- **Security Group**: fsx-netapp-ontap-sg
- **NFS Port**: 2049 (allowed from SageMaker security group)

## Scaling for Production

To scale the FSx volume for production use (up to 800 TiB):

1. Update `storage_capacity` in `fsx_stack.py`:
   ```python
   storage_capacity=819200,  # 800 TiB in GiB
   ```

2. Update volume size:
   ```python
   size_in_megabytes="838860800",  # 800 TiB in MiB
   ```

3. Consider increasing throughput capacity:
   ```python
   throughput_capacity=512,  # or higher
   ```

4. Redeploy the stack:
   ```bash
   npx cdk deploy CrossAzFsxSageMakerFsx
   ```

## Monitoring

CloudWatch metrics are automatically enabled for FSx. Key metrics to monitor:

- **DataReadBytes**: Bytes read from the file system
- **DataWriteBytes**: Bytes written to the file system
- **DataReadOperations**: Number of read operations
- **DataWriteOperations**: Number of write operations
- **StorageCapacity**: Total storage capacity
- **StorageUsed**: Storage currently in use

Access metrics in CloudWatch console under FSx namespace.

## Cost Estimation

### Testing Configuration (1 TiB)
- Storage: ~$200/month (1024 GiB × $0.20/GiB-month)
- Throughput: ~$50/month (128 MBps)
- **Total**: ~$250/month

### Production Configuration (800 TiB)
- Storage: ~$160,000/month (800 TiB × $0.20/GiB-month)
- Throughput: ~$200/month (512 MBps)
- **Total**: ~$160,200/month

### Cross-AZ Data Transfer
- $0.01/GB for data transfer between AZs
- Example: 100 GB transfer = $1.00

## Troubleshooting

### Mount Fails with "Connection Refused"

Check security group rules:
```bash
aws ec2 describe-security-groups \
  --group-names fsx-netapp-ontap-sg \
  --query 'SecurityGroups[0].IpPermissions'
```

Ensure port 2049 is open from SageMaker security group.

### Mount Fails with "Permission Denied"

Verify the volume security style is UNIX:
```bash
aws fsx describe-volumes \
  --volume-ids <VOLUME-ID> \
  --query 'Volumes[0].OntapConfiguration.SecurityStyle'
```

### Slow Performance

Check throughput capacity and consider increasing:
```bash
aws fsx describe-file-systems \
  --file-system-ids <FS-ID> \
  --query 'FileSystems[0].OntapConfiguration.ThroughputCapacity'
```

## Cleanup

To delete the FSx stack and avoid ongoing charges:

```bash
cd infrastructure
npx cdk destroy CrossAzFsxSageMakerFsx
```

**Warning**: This will permanently delete the file system and all data stored on it.

## NFS Export Configuration

After deploying the FSx stack, you need to configure NFS export policies to allow SageMaker Training Jobs to access the volume. See the detailed guide:

**[NFS Export Configuration Guide](NFS_EXPORT_CONFIGURATION.md)**

Quick steps:

1. Generate export policy commands:
   ```bash
   python configure_nfs_export.py --svm-id <SVM-ID> --vpc-id <VPC-ID>
   ```

2. Execute commands via ONTAP CLI (see guide for details)

3. Verify configuration:
   ```bash
   python verify_nfs_export.py --svm-id <SVM-ID>
   ```

## Next Steps

1. ✅ Configure NFS export permissions (Task 1.5) - See [NFS_EXPORT_CONFIGURATION.md](NFS_EXPORT_CONFIGURATION.md)
2. Enable CloudWatch monitoring (Task 1.6)
3. Prepare test data (Phase 2)
4. Execute cross-AZ validation tests (Phase 6)
