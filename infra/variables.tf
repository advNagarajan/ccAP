variable "project_id" {
  description = "The GCP Project ID where resources will be created"
  type        = string
  default     = "project-8bf9e75e-8d66-4f87-a96"
}

variable "region" {
  description = "The target GCP region"
  type        = string
  default     = "asia-south1"
}

variable "frontend_bucket_name" {
  description = "The name of the static frontend hosting bucket (must be globally unique)"
  type        = string
  default     = "data-landing-platform-frontend"
}

variable "landing_bucket_name" {
  description = "The name of the raw data landing bucket"
  type        = string
  default     = "dataset-platform-landing"
}

variable "artifact_repository_name" {
  description = "The name of the Artifact Registry Docker repository"
  type        = string
  default     = "data-landing-platform"
}

variable "github_deployer_sa_name" {
  description = "The service account ID for GitHub Actions deployment"
  type        = string
  default     = "github-deployer"
}

variable "db_agent_sa_name" {
  description = "The service account ID for BigQuery & Firestore data agent"
  type        = string
  default     = "demo2-536"
}

variable "pubsub_topics" {
  description = "List of Pub/Sub topics required for orchestration"
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

variable "secrets" {
  description = "List of Secret Manager secrets to register"
  type        = list(string)
  default = [
    "DB_PASSWORD",
    "DB_USER",
    "SLACK_WEBHOOK_URL",
    "SLACK_WEBHOOK_DEAD_LETTER",
    "SLACK_WEBHOOK_NEW_TABLE",
    "SLACK_WEBHOOK_JOB_COMPLETED",
    "SLACK_WEBHOOK_JOB_FAILED",
    "SLACK_WEBHOOK_QUALITY_CHECK",
    "SMTP_USER",
    "SMTP_PASSWORD"
  ]
}
