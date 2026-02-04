variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "role_name" {
  description = "Name for the SageMaker execution role"
  type        = string
  default     = "SageMakerFinetuningRole"

  validation {
    condition     = can(regex("^[\\w+=,.@-]+$", var.role_name))
    error_message = "Role name must contain only alphanumeric characters and +=,.@-"
  }
}

variable "s3_bucket_name" {
  description = "Name of the S3 bucket for training data and model artifacts"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]*[a-z0-9]$", var.s3_bucket_name))
    error_message = "Bucket name must be lowercase, alphanumeric, and hyphens only"
  }
}

variable "enable_vpc_access" {
  description = "Enable VPC access for SageMaker (requires EC2 network interface permissions)"
  type        = bool
  default     = false
}

variable "enable_kms_encryption" {
  description = "Enable KMS encryption for S3"
  type        = bool
  default     = false
}

variable "kms_key_arn" {
  description = "ARN of KMS key for S3 encryption (only if enable_kms_encryption is true)"
  type        = string
  default     = ""

  validation {
    condition     = var.kms_key_arn == "" || can(regex("^arn:aws:kms:", var.kms_key_arn))
    error_message = "KMS key ARN must be a valid ARN starting with 'arn:aws:kms:'"
  }
}

variable "tags" {
  description = "Additional tags to apply to resources"
  type        = map(string)
  default     = {}
}
