# Quick Start Guide

Get the cross-AZ FSx SageMaker validation infrastructure up and running in minutes.

## Prerequisites

- AWS account with admin access
- AWS CLI configured (`aws configure`)
- Python 3.8+ installed
- Node.js and npm installed (for CDK CLI)

## 5-Minute Setup

### 1. Install CDK CLI
```bash
npm install -g aws-cdk
```

### 2. Install Python Dependencies
```bash
cd infrastructure
pip install -r requirements.txt
```

### 3. Bootstrap CDK (First Time Only)
```bash
# Replace ACCOUNT-ID with your AWS account ID
cdk bootstrap aws://ACCOUNT-ID/us-west-2
```

### 4. Deploy Infrastructure
```bash
./deploy.sh
```

Or manually:
```bash
cdk synth
cdk deploy
```

### 5. Verify Deployment
```bash
python verify_deployment.py
```

## What Gets Created

- ✅ VPC (10.0.0.0/16) in us-west-2
- ✅ Subnet in us-west-2a (for FSx)
- ✅ Subnet in us-west-2b (for SageMaker)
- ✅ Internet Gateway
- ✅ Route tables

## Expected Output

After deployment, you'll see:
```
Outputs:
CrossAzFsxSageMakerNetwork.VpcId = vpc-xxxxx
CrossAzFsxSageMakerNetwork.FsxSubnetId = subnet-xxxxx
CrossAzFsxSageMakerNetwork.SageMakerSubnetId = subnet-xxxxx
CrossAzFsxSageMakerNetwork.FsxSubnetCidr = 10.0.0.0/24
CrossAzFsxSageMakerNetwork.SageMakerSubnetCidr = 10.0.1.0/24
```

Save these values - you'll need them for subsequent tasks!

## Next Steps

1. Configure security groups (Task 1.2)
2. Create IAM roles (Task 1.3)
3. Deploy FSx NetApp ONTAP (Task 1.4)

## Cleanup

When you're done with validation:
```bash
./destroy.sh
```

Or manually:
```bash
cdk destroy
```

## Troubleshooting

**Problem**: `cdk: command not found`  
**Solution**: Install CDK CLI: `npm install -g aws-cdk`

**Problem**: `Unable to resolve AWS account`  
**Solution**: Run `aws configure` and set your credentials

**Problem**: `CDK bootstrap required`  
**Solution**: Run `cdk bootstrap aws://ACCOUNT-ID/us-west-2`

## Cost

This infrastructure costs approximately:
- **VPC/Subnets/IGW**: $0/month (free)
- **Cross-AZ data transfer**: $0.01/GB (only during validation)

## Documentation

- [README.md](README.md) - Detailed deployment guide
- [ARCHITECTURE.md](ARCHITECTURE.md) - Architecture details
- [TASK_1.1_SUMMARY.md](TASK_1.1_SUMMARY.md) - Task completion summary

## Support

For issues or questions:
1. Check [ARCHITECTURE.md](ARCHITECTURE.md) for design details
2. Review [TASK_1.1_SUMMARY.md](TASK_1.1_SUMMARY.md) troubleshooting section
3. Verify AWS credentials and permissions
