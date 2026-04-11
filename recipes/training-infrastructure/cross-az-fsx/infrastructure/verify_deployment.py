#!/usr/bin/env python3
"""
Verify that the VPC and subnets are correctly deployed
"""
import boto3
import sys

def verify_deployment():
    """Verify VPC and subnet deployment in us-west-2"""
    ec2 = boto3.client('ec2', region_name='us-west-2')
    
    print("=== Verifying Cross-AZ FSx SageMaker Infrastructure ===\n")
    
    # Find VPC by name
    vpcs = ec2.describe_vpcs(
        Filters=[
            {'Name': 'tag:Name', 'Values': ['cross-az-fsx-sagemaker-vpc']}
        ]
    )
    
    if not vpcs['Vpcs']:
        print("❌ VPC not found")
        return False
    
    vpc = vpcs['Vpcs'][0]
    vpc_id = vpc['VpcId']
    print(f"✓ VPC found: {vpc_id}")
    print(f"  CIDR: {vpc['CidrBlock']}\n")
    
    # Find subnets
    subnets = ec2.describe_subnets(
        Filters=[
            {'Name': 'vpc-id', 'Values': [vpc_id]}
        ]
    )
    
    fsx_subnet = None
    sagemaker_subnet = None
    
    for subnet in subnets['Subnets']:
        az = subnet['AvailabilityZone']
        subnet_id = subnet['SubnetId']
        cidr = subnet['CidrBlock']
        
        if az == 'us-west-2a':
            fsx_subnet = subnet
            print(f"✓ FSx Subnet (us-west-2a): {subnet_id}")
            print(f"  CIDR: {cidr}\n")
        elif az == 'us-west-2b':
            sagemaker_subnet = subnet
            print(f"✓ SageMaker Subnet (us-west-2b): {subnet_id}")
            print(f"  CIDR: {cidr}\n")
    
    if not fsx_subnet:
        print("❌ FSx subnet in us-west-2a not found")
        return False
    
    if not sagemaker_subnet:
        print("❌ SageMaker subnet in us-west-2b not found")
        return False
    
    # Check internet gateway
    igws = ec2.describe_internet_gateways(
        Filters=[
            {'Name': 'attachment.vpc-id', 'Values': [vpc_id]}
        ]
    )
    
    if igws['InternetGateways']:
        igw_id = igws['InternetGateways'][0]['InternetGatewayId']
        print(f"✓ Internet Gateway: {igw_id}\n")
    else:
        print("⚠ No Internet Gateway found\n")
    
    print("=== Verification Complete ===")
    print("\nInfrastructure is ready for:")
    print("  - Task 1.2: Configure security groups for NFS access")
    print("  - Task 1.3: Create IAM roles for SageMaker")
    print("  - Task 1.4: Deploy FSx NetApp ONTAP in us-west-2a")
    
    return True

if __name__ == '__main__':
    try:
        success = verify_deployment()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
