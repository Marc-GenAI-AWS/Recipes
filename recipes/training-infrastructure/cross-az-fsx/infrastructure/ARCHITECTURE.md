# Infrastructure Architecture

## Overview

This infrastructure supports the cross-AZ FSx SageMaker validation project, which validates that SageMaker Training Jobs can access FSx NetApp ONTAP storage across availability zones without data replication.

## Network Design

### VPC Configuration
- **CIDR Block**: 10.0.0.0/16
- **Region**: us-west-2
- **Availability Zones**: us-west-2a, us-west-2b

### Subnets

#### FSx Subnet (us-west-2a)
- **Purpose**: Host FSx NetApp ONTAP file system
- **CIDR**: 10.0.0.0/24 (assigned by CDK)
- **Type**: Public subnet with Internet Gateway access
- **Resources**: FSx NetApp ONTAP volume (800TB capacity)

#### SageMaker Subnet (us-west-2b)
- **Purpose**: Host P5 SageMaker Training Jobs
- **CIDR**: 10.0.1.0/24 (assigned by CDK)
- **Type**: Public subnet with Internet Gateway access
- **Resources**: SageMaker Training Jobs on P5 instances

### Routing

Both subnets have route tables configured with:
- Local route for VPC CIDR (10.0.0.0/16)
- Default route (0.0.0.0/0) to Internet Gateway

This allows:
- Cross-AZ communication between subnets
- Outbound internet access for downloading data and container images
- Inbound access if needed (controlled by security groups)

## Cross-AZ Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    VPC: 10.0.0.0/16                         │
│                                                             │
│  ┌──────────────────────┐      ┌──────────────────────┐   │
│  │   us-west-2a         │      │   us-west-2b         │   │
│  │   10.0.0.0/24        │      │   10.0.1.0/24        │   │
│  │                      │      │                      │   │
│  │  ┌────────────────┐  │      │  ┌────────────────┐  │   │
│  │  │ FSx NetApp     │  │      │  │ SageMaker      │  │   │
│  │  │ ONTAP          │◄─┼──────┼──┤ Training Job   │  │   │
│  │  │ (800TB)        │  │ NFS  │  │ (P5 Instance)  │  │   │
│  │  └────────────────┘  │      │  └────────────────┘  │   │
│  │                      │      │                      │   │
│  └──────────────────────┘      └──────────────────────┘   │
│                                                             │
│                    Internet Gateway                         │
└─────────────────────────────────────────────────────────────┘
```

## Design Decisions

### Why Public Subnets?

Public subnets are used for simplicity and cost optimization:
- No NAT Gateway costs (~$32/month per AZ)
- Direct internet access for downloading genomic data from UCSC
- Direct access for pulling BioNeMo container images from NGC
- Security controlled via security groups (configured in Task 1.2)

For production deployments, consider private subnets with VPC endpoints.

### Why No NAT Gateway?

NAT Gateways are not required because:
- Resources need direct internet access for data downloads
- Cross-AZ communication uses VPC local routing (no NAT needed)
- Security groups provide sufficient access control
- Cost savings: ~$64/month (2 AZs × $32/month)

### Availability Zone Selection

- **us-west-2a**: Selected for FSx deployment (arbitrary choice)
- **us-west-2b**: Selected for P5 instances (based on availability)

Note: P5 instance availability should be verified before deployment (Task 1.7).

## Cost Considerations

### Network Infrastructure Costs

- **VPC**: Free
- **Subnets**: Free
- **Internet Gateway**: Free
- **Data Transfer**:
  - Inbound: Free
  - Outbound to internet: $0.09/GB (first 10TB)
  - Cross-AZ transfer: $0.01/GB (measured during validation)

### Estimated Monthly Costs

For validation phases (10GB → 2TB):
- Cross-AZ data transfer: $0.01/GB × data volume
- Example: 2TB validation = $20.48 in cross-AZ transfer costs

For production (800TB):
- Cross-AZ transfer per training job: Depends on data access patterns
- Storage: FSx NetApp ONTAP costs (separate from network)

## Security Considerations

### Current Configuration

- Public subnets with Internet Gateway
- No default security group rules (configured in Task 1.2)
- No network ACLs (default allow all)

### Next Steps (Task 1.2)

Security groups will be configured to:
- Allow NFS traffic (port 2049) between subnets
- Allow HTTPS (port 443) for AWS API calls
- Allow SSH (port 22) for debugging if needed
- Deny all other inbound traffic

### Production Recommendations

For production deployments:
- Use private subnets with VPC endpoints
- Enable VPC Flow Logs for network monitoring
- Implement network ACLs for additional security layer
- Use AWS PrivateLink for AWS service access
- Enable encryption in transit for NFS (Kerberos or VPN)

## Deployment

See [README.md](README.md) for deployment instructions.

## Verification

After deployment, verify the infrastructure:

```bash
python verify_deployment.py
```

This checks:
- VPC exists with correct CIDR
- Subnets exist in correct AZs
- Internet Gateway is attached
- Resources are properly tagged

## Next Tasks

After completing Task 1.1 (this infrastructure):

1. **Task 1.2**: Configure security groups for cross-AZ NFS access
2. **Task 1.3**: Create IAM roles for SageMaker with FSx permissions
3. **Task 1.4**: Deploy FSx NetApp ONTAP in us-west-2a subnet
4. **Task 1.5**: Configure FSx NFS export
5. **Task 1.6**: Enable CloudWatch monitoring
6. **Task 1.7**: Verify P5 instance availability in us-west-2b

## Troubleshooting

### CDK Bootstrap Issues

If deployment fails with "CDK bootstrap" error:
```bash
cdk bootstrap aws://ACCOUNT-ID/us-west-2
```

### Subnet AZ Assignment Issues

CDK automatically assigns subnets to AZs. If specific AZ assignment is critical, verify after deployment using:
```bash
aws ec2 describe-subnets --filters "Name=vpc-id,Values=VPC-ID"
```

### Internet Gateway Not Attached

If Internet Gateway is not attached to VPC:
```bash
aws ec2 attach-internet-gateway --vpc-id VPC-ID --internet-gateway-id IGW-ID
```

## References

- [AWS VPC Documentation](https://docs.aws.amazon.com/vpc/)
- [AWS CDK VPC Construct](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_ec2/Vpc.html)
- [FSx NetApp ONTAP Networking](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/supported-fsx-clients.html)
- [SageMaker VPC Configuration](https://docs.aws.amazon.com/sagemaker/latest/dg/train-vpc.html)
