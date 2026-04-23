output "role_arn" {
  description = "ARN of the SageMaker execution role"
  value       = aws_iam_role.sagemaker_execution_role.arn
}

output "role_name" {
  description = "Name of the SageMaker execution role"
  value       = aws_iam_role.sagemaker_execution_role.name
}

output "role_id" {
  description = "Unique ID of the SageMaker execution role"
  value       = aws_iam_role.sagemaker_execution_role.id
}

output "s3_bucket_name" {
  description = "S3 bucket name configured for this role"
  value       = var.s3_bucket_name
}

output "configuration_instructions" {
  description = "Next steps to configure the pipeline"
  value       = <<-EOT
    1. Copy the Role ARN: ${aws_iam_role.sagemaker_execution_role.arn}
    2. Update config/pipeline_config.yaml with:
       aws:
         sagemaker_role_arn: ${aws_iam_role.sagemaker_execution_role.arn}
         s3_bucket: ${var.s3_bucket_name}
    3. Ensure S3 bucket ${var.s3_bucket_name} exists in your account
    4. Run validation: python config/aws/scripts/validate_permissions.py --role-arn ${aws_iam_role.sagemaker_execution_role.arn}
  EOT
}
