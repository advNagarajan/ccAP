# =========================================================================
# AWS INFRASTRUCTURE VARIABLES
# =========================================================================

variable "aws_region" {
  description = "The target AWS region"
  type        = string
  default     = "ap-southeast-2"
}

variable "environment" {
  description = "Environment identifier (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name identifier"
  type        = string
  default     = "data-landing-platform"
}

variable "landing_bucket_prefix" {
  description = "Prefix for the raw dataset S3 landing bucket"
  type        = string
  default     = "dataset-platform-landing"
}

variable "frontend_bucket_prefix" {
  description = "Prefix for the static React web hosting S3 bucket"
  type        = string
  default     = "data-landing-platform-frontend"
}

variable "ecr_repository_name" {
  description = "Name of the AWS Elastic Container Registry (ECR) repository"
  type        = string
  default     = "data-landing-platform"
}

variable "db_name" {
  description = "Name of the PostgreSQL database"
  type        = string
  default     = "metadata_db"
}

variable "db_username" {
  description = "Master username for PostgreSQL database"
  type        = string
  default     = "postgres"
}

variable "db_password" {
  description = "Master password for PostgreSQL database"
  type        = string
  sensitive   = true
  default     = "DataLandingPass123!"
}

# =========================================================================
# SNS TOPICS (1:1 with GCP Pub/Sub topics)
# =========================================================================
variable "topics" {
  description = "List of SNS topics required for pipeline orchestration"
  type        = list(string)
  default = [
    "ingestion-requested",
    "dataset-received",
    "metadata-extracted",
    "metadata-vectorized",
    "profile-generated",
    "schema-inferred",
    "schema-validated",
    "drift-detected",
    "recommendation-generated",
    "target-inferred",
    "target-mutated",
    "target-mapped",
    "target-updated",
    "feedback-submitted",
    "job-completed",
    "job-failed",
    "job-failures-dead-letter-topic",
    "quality-check-completed",
    "quality-check-requested",
    "fallback-requested",
    "context-generated"
  ]
}

# =========================================================================
# EC2 COMPUTE & SLACK NOTIFICATION VARIABLES
# =========================================================================
variable "instance_type" {
  description = "EC2 instance type for backend API and continuous worker daemons"
  type        = string
  default     = "t3.micro"
}

variable "slack_webhook_url" {
  description = "Slack Webhook URL for general notifications"
  type        = string
  default     = ""
}

variable "slack_webhook_job_completed" {
  description = "Slack Webhook URL for job completed"
  type        = string
  default     = ""
}

variable "slack_webhook_job_failed" {
  description = "Slack Webhook URL for job failed"
  type        = string
  default     = ""
}

variable "slack_webhook_quality_check" {
  description = "Slack Webhook URL for quality check results"
  type        = string
  default     = ""
}

variable "slack_webhook_dead_letter" {
  description = "Slack Webhook URL for dead-letter poison pills"
  type        = string
  default     = ""
}

variable "slack_webhook_new_table" {
  description = "Slack Webhook URL for new table mutations and drift"
  type        = string
  default     = ""
}
