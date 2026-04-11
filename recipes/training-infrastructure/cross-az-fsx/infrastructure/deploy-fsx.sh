#!/bin/bash
# Deploy FSx infrastructure for cross-AZ validation

set -e

echo "=========================================="
echo "FSx Infrastructure Deployment"
echo "=========================================="
echo ""

# Check if AWS credentials are configured
echo "Checking AWS credentials..."
aws sts get-caller-identity > /dev/null 2>&1 || {
    echo "ERROR: AWS credentials not configured"
    echo "Please run: aws configure"
    exit 1
}

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="us-west-2"

echo "Account ID: $ACCOUNT_ID"
echo "Region: $REGION"
echo ""

# Bootstrap CDK if needed
echo "Checking CDK bootstrap status..."
if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region $REGION > /dev/null 2>&1; then
    echo "Bootstrapping CDK..."
    npx cdk bootstrap aws://$ACCOUNT_ID/$REGION
else
    echo "CDK already bootstrapped"
fi
echo ""

# Deploy stacks in order
echo "=========================================="
echo "Deploying Network Stack..."
echo "=========================================="
npx cdk deploy CrossAzFsxSageMakerNetwork --require-approval never

echo ""
echo "=========================================="
echo "Deploying IAM Stack..."
echo "=========================================="
npx cdk deploy CrossAzFsxSageMakerIam --require-approval never

echo ""
echo "=========================================="
echo "Deploying FSx Stack..."
echo "=========================================="
echo "NOTE: FSx deployment takes 20-30 minutes"
npx cdk deploy CrossAzFsxSageMakerFsx --require-approval never

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""

# Get FSx information
echo "Retrieving FSx connection information..."
SVM_ID=$(aws cloudformation describe-stacks \
  --stack-name CrossAzFsxSageMakerFsx \
  --query 'Stacks[0].Outputs[?OutputKey==`StorageVirtualMachineId`].OutputValue' \
  --output text)

if [ -n "$SVM_ID" ]; then
    echo "Storage Virtual Machine ID: $SVM_ID"
    echo ""
    echo "Waiting for SVM to be available..."
    aws fsx wait storage-virtual-machine-available --storage-virtual-machine-ids $SVM_ID
    
    SVM_DNS=$(aws fsx describe-storage-virtual-machines \
      --storage-virtual-machine-ids $SVM_ID \
      --query 'StorageVirtualMachines[0].Endpoints.Nfs.DNSName' \
      --output text)
    
    echo ""
    echo "=========================================="
    echo "FSx Connection Information"
    echo "=========================================="
    echo "SVM DNS Name: $SVM_DNS"
    echo "Mount Path: /genomics"
    echo ""
    echo "Mount Command:"
    echo "  sudo mount -t nfs $SVM_DNS:/genomics /mnt/fsx"
    echo ""
fi

echo "Deployment complete! FSx is ready for use."
