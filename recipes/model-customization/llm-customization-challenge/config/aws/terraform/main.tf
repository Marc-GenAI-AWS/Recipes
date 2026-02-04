terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}

# Data source for current AWS region
data "aws_region" "current" {}

# IAM Role for SageMaker
resource "aws_iam_role" "sagemaker_execution_role" {
  name        = var.role_name
  description = "Execution role for SageMaker LLM finetuning pipeline with least privilege permissions"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "sagemaker.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })

  tags = {
    Purpose   = "SageMaker-Finetuning"
    ManagedBy = "Terraform"
    Project   = "LLM-Finetuning-Pipeline"
  }
}

# S3 Access Policy
resource "aws_iam_role_policy" "s3_access" {
  name = "S3AccessPolicy"
  role = aws_iam_role.sagemaker_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3BucketAccess"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = [
          "arn:aws:s3:::${var.s3_bucket_name}"
        ]
      },
      {
        Sid    = "S3ObjectAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "arn:aws:s3:::${var.s3_bucket_name}/*"
        ]
      },
      {
        Sid    = "S3ListAllBuckets"
        Effect = "Allow"
        Action = [
          "s3:ListAllMyBuckets"
        ]
        Resource = "*"
      }
    ]
  })
}

# Bedrock Access Policy
resource "aws_iam_role_policy" "bedrock_access" {
  name = "BedrockAccessPolicy"
  role = aws_iam_role.sagemaker_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BedrockModelInvocation"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-4-*",
          "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-*"
        ]
      },
      {
        Sid    = "BedrockModelInfo"
        Effect = "Allow"
        Action = [
          "bedrock:GetFoundationModel",
          "bedrock:ListFoundationModels"
        ]
        Resource = "*"
      }
    ]
  })
}

# CloudWatch Logs Policy
resource "aws_iam_role_policy" "cloudwatch_logs" {
  name = "CloudWatchLogsPolicy"
  role = aws_iam_role.sagemaker_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogsAccess"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = [
          "arn:aws:logs:*:${data.aws_caller_identity.current.account_id}:log-group:/aws/sagemaker/*",
          "arn:aws:logs:*:${data.aws_caller_identity.current.account_id}:log-group:FinetuningPipeline/*"
        ]
      },
      {
        Sid    = "CloudWatchMetrics"
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = [
              "AWS/SageMaker",
              "FinetuningPipeline/Dev",
              "FinetuningPipeline/Prod"
            ]
          }
        }
      }
    ]
  })
}

# SageMaker Execution Policy
resource "aws_iam_role_policy" "sagemaker_execution" {
  name = "SageMakerExecutionPolicy"
  role = aws_iam_role.sagemaker_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SageMakerTraining"
        Effect = "Allow"
        Action = [
          "sagemaker:CreateTrainingJob",
          "sagemaker:DescribeTrainingJob",
          "sagemaker:StopTrainingJob",
          "sagemaker:ListTrainingJobs"
        ]
        Resource = [
          "arn:aws:sagemaker:*:${data.aws_caller_identity.current.account_id}:training-job/*"
        ]
      },
      {
        Sid    = "SageMakerModel"
        Effect = "Allow"
        Action = [
          "sagemaker:CreateModel",
          "sagemaker:DescribeModel",
          "sagemaker:DeleteModel",
          "sagemaker:ListModels"
        ]
        Resource = [
          "arn:aws:sagemaker:*:${data.aws_caller_identity.current.account_id}:model/*"
        ]
      },
      {
        Sid    = "SageMakerEndpointConfig"
        Effect = "Allow"
        Action = [
          "sagemaker:CreateEndpointConfig",
          "sagemaker:DescribeEndpointConfig",
          "sagemaker:DeleteEndpointConfig"
        ]
        Resource = [
          "arn:aws:sagemaker:*:${data.aws_caller_identity.current.account_id}:endpoint-config/*"
        ]
      },
      {
        Sid    = "SageMakerEndpoint"
        Effect = "Allow"
        Action = [
          "sagemaker:CreateEndpoint",
          "sagemaker:DescribeEndpoint",
          "sagemaker:DeleteEndpoint",
          "sagemaker:UpdateEndpoint",
          "sagemaker:InvokeEndpoint",
          "sagemaker:ListEndpoints"
        ]
        Resource = [
          "arn:aws:sagemaker:*:${data.aws_caller_identity.current.account_id}:endpoint/*"
        ]
      },
      {
        Sid    = "SageMakerJumpStart"
        Effect = "Allow"
        Action = [
          "sagemaker:ListModelPackages",
          "sagemaker:DescribeModelPackage"
        ]
        Resource = "*"
      },
      {
        Sid    = "ECRAccess"
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      }
    ]
  })
}

# VPC Access Policy (conditional)
resource "aws_iam_role_policy" "vpc_access" {
  count = var.enable_vpc_access ? 1 : 0
  name  = "VPCAccessPolicy"
  role  = aws_iam_role.sagemaker_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EC2NetworkInterfaces"
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:CreateNetworkInterfacePermission",
          "ec2:DeleteNetworkInterface",
          "ec2:DeleteNetworkInterfacePermission",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DescribeVpcs",
          "ec2:DescribeDhcpOptions",
          "ec2:DescribeSubnets",
          "ec2:DescribeSecurityGroups"
        ]
        Resource = "*"
      }
    ]
  })
}

# KMS Access Policy (conditional)
resource "aws_iam_role_policy" "kms_access" {
  count = var.enable_kms_encryption && var.kms_key_arn != "" ? 1 : 0
  name  = "KMSAccessPolicy"
  role  = aws_iam_role.sagemaker_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "KMSEncryption"
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey"
        ]
        Resource = var.kms_key_arn
      }
    ]
  })
}
