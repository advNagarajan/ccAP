# =========================================================================
# AWS DEPLOYMENT OUTPUTS
# =========================================================================

output "rds_address" {
  description = "The PostgreSQL database server hostname (Use this for DB_HOST)"
  value       = aws_db_instance.postgres.address
}

output "rds_port" {
  description = "The PostgreSQL database port"
  value       = aws_db_instance.postgres.port
}

output "ecr_repository_url" {
  description = "The ECR repository URL for backend Docker images"
  value       = aws_ecr_repository.repo.repository_url
}

output "landing_s3_bucket" {
  description = "The S3 bucket name for raw ingested datasets"
  value       = aws_s3_bucket.landing_bucket.id
}

output "frontend_s3_bucket" {
  description = "The S3 bucket name for hosting the React frontend"
  value       = aws_s3_bucket.frontend_bucket.id
}

output "cloudfront_domain_name" {
  description = "The public CloudFront CDN URL for your live React web app"
  value       = "https://${aws_cloudfront_distribution.frontend_cdn.domain_name}"
}

output "cloudfront_distribution_id" {
  description = "The CloudFront Distribution ID (for cache invalidation)"
  value       = aws_cloudfront_distribution.frontend_cdn.id
}

output "aws_access_key_id" {
  description = "AWS Access Key ID for GitHub Actions"
  value       = aws_iam_access_key.github_deployer_key.id
}

output "aws_secret_access_key" {
  description = "AWS Secret Access Key for GitHub Actions"
  value       = aws_iam_access_key.github_deployer_key.secret
  sensitive   = true
}

output "server_public_ip" {
  description = "Public IPv4 address of the EC2 backend & worker server"
  value       = aws_instance.server.public_ip
}

output "server_public_dns" {
  description = "Public DNS hostname of the EC2 backend & worker server"
  value       = aws_instance.server.public_dns
}

output "api_url" {
  description = "Public URL for the FastAPI backend"
  value       = "http://${aws_instance.server.public_ip}:8000"
}



