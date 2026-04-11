#!/bin/bash
# Build and push FSx validation container to ECR

set -e

# Configuration
REGION="us-west-2"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REPOSITORY_NAME="fsx-validation"
IMAGE_TAG="latest"

echo "=========================================="
echo "Building FSx Validation Container"
echo "=========================================="
echo "Account ID: $ACCOUNT_ID"
echo "Region: $REGION"
echo "Repository: $REPOSITORY_NAME"
echo ""

# Create ECR repository if it doesn't exist
echo "Creating ECR repository (if needed)..."
aws ecr describe-repositories --repository-names $REPOSITORY_NAME --region $REGION 2>/dev/null || \
    aws ecr create-repository --repository-name $REPOSITORY_NAME --region $REGION

# Get ECR login
echo "Logging in to ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

# Build Docker image
echo "Building Docker image..."
docker build -t $REPOSITORY_NAME:$IMAGE_TAG .

# Tag image
echo "Tagging image..."
docker tag $REPOSITORY_NAME:$IMAGE_TAG $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPOSITORY_NAME:$IMAGE_TAG

# Push to ECR
echo "Pushing to ECR..."
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPOSITORY_NAME:$IMAGE_TAG

echo ""
echo "=========================================="
echo "Container pushed successfully!"
echo "=========================================="
echo "Image URI: $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPOSITORY_NAME:$IMAGE_TAG"
echo ""
echo "You can now launch a training job with:"
echo "  python ../launch_test_training_job.py \\"
echo "    --job-name test-cross-az-validation \\"
echo "    --fsx-file-system-id fs-04b3f909e86004fc2 \\"
echo "    --data-subdir phase_10gb"
echo ""
