#!/bin/bash
# Deployment script for cross-AZ FSx SageMaker validation infrastructure

set -e

echo "=== Cross-AZ FSx SageMaker Validation Infrastructure Deployment ==="
echo ""

# Check if CDK is installed
if ! command -v cdk &> /dev/null; then
    echo "Error: AWS CDK CLI is not installed"
    echo "Install it with: npm install -g aws-cdk"
    exit 1
fi

# Check if Python dependencies are installed
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Synthesize CloudFormation template
echo ""
echo "Synthesizing CloudFormation template..."
cdk synth

# Deploy the stack
echo ""
echo "Deploying infrastructure stack..."
cdk deploy --require-approval never

echo ""
echo "=== Deployment Complete ==="
echo "Check the outputs above for VPC and subnet IDs"
