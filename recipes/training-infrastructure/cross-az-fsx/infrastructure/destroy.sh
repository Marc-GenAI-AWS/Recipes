#!/bin/bash
# Cleanup script for cross-AZ FSx SageMaker validation infrastructure

set -e

echo "=== Cross-AZ FSx SageMaker Validation Infrastructure Cleanup ==="
echo ""
echo "WARNING: This will destroy all infrastructure resources"
echo ""

read -p "Are you sure you want to destroy the infrastructure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Cleanup cancelled"
    exit 0
fi

echo ""
echo "Destroying infrastructure stack..."
cdk destroy --force

echo ""
echo "=== Cleanup Complete ==="
