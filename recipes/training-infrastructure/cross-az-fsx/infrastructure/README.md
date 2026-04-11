# Cross-AZ FSx SageMaker Validation Infrastructure

This directory contains AWS CDK infrastructure code for the cross-AZ FSx SageMaker validation project.

## Architecture

The infrastructure creates:
- VPC with CIDR 10.0.0.0/16
- Public subnet in us-west-2a (for FSx NetApp ONTAP)
- Public subnet in us-west-2b (for P5 SageMaker Training Jobs)
- Internet Gateway for external access
- Route tables configured for both subnets

## Prerequisites

- Python 3.8 or later
- AWS CLI configured with appropriate credentials
- AWS CDK CLI installed (`npm install -g aws-cdk`)
- AWS account with permissions to create VPC resources

## Setup

1. Install Python dependencies:
```bash
cd infrastructure
pip install -r requirements.txt
```

2. Bootstrap CDK (first time only):
```bash
cdk bootstrap aws://ACCOUNT-ID/us-west-2
```

## Deployment

1. Synthesize CloudFormation template:
```bash
cdk synth
```

2. Deploy the stack:
```bash
cdk deploy
```

3. View outputs:
After deployment, the stack outputs will show:
- VPC ID
- FSx Subnet ID (us-west-2a)
- SageMaker Subnet ID (us-west-2b)
- CIDR blocks for both subnets

## Cleanup

To destroy the infrastructure:
```bash
cdk destroy
```

## Stack Outputs

The stack provides the following outputs:
- `VpcId`: The ID of the created VPC
- `FsxSubnetId`: Subnet ID in us-west-2a for FSx deployment
- `SageMakerSubnetId`: Subnet ID in us-west-2b for SageMaker Training Jobs
- `FsxSubnetCidr`: CIDR block for the FSx subnet
- `SageMakerSubnetCidr`: CIDR block for the SageMaker subnet

## Next Steps

After deploying this network infrastructure:
1. Configure security groups for cross-AZ NFS access (Task 1.2)
2. Create IAM roles for SageMaker (Task 1.3)
3. Deploy FSx NetApp ONTAP in us-west-2a subnet (Task 1.4)
