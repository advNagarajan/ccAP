# =========================================================================
# AZURE INFRASTRUCTURE VARIABLES
# =========================================================================

variable "resource_group_name" {
  description = "Name of the Azure Resource Group"
  type        = string
  default     = "rg-data-landing-platform"
}

variable "location" {
  description = "The Azure region to deploy resources into"
  type        = string
  default     = "eastus"
}

variable "environment" {
  description = "Environment name (e.g. dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project identifier"
  type        = string
  default     = "data-landing-platform"
}

variable "frontend_storage_name" {
  description = "Globally unique name for frontend static hosting storage account (letters and numbers only, max 24 chars)"
  type        = string
  default     = "datalandingfe"
}

variable "landing_storage_name" {
  description = "Globally unique name for raw landing storage account (letters and numbers only, max 24 chars)"
  type        = string
  default     = "datalandingraw"
}

variable "acr_name" {
  description = "Name of the Azure Container Registry (alphanumeric only, 5-50 chars)"
  type        = string
  default     = "datalandingacr"
}

variable "servicebus_namespace_name" {
  description = "Name of the Azure Service Bus namespace"
  type        = string
  default     = "sb-data-landing-platform"
}

variable "keyvault_name" {
  description = "Name of the Azure Key Vault (must be globally unique, 3-24 chars)"
  type        = string
  default     = "kv-datalanding"
}

variable "postgres_server_name" {
  description = "Name of the PostgreSQL Flexible Server"
  type        = string
  default     = "psql-data-landing-platform"
}

variable "postgres_admin_username" {
  description = "Administrator username for PostgreSQL Flexible Server"
  type        = string
  default     = "pgadmin"
}

variable "postgres_admin_password" {
  description = "Administrator password for PostgreSQL Flexible Server"
  type        = string
  sensitive   = true
  default     = "ChangeMeP@ssw0rd123!"
}

# =========================================================================
# SERVICE BUS TOPICS (1:1 with GCP Pub/Sub topics)
# =========================================================================
variable "servicebus_topics" {
  description = "List of Service Bus topics required for pipeline orchestration"
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
# KEY VAULT SECRETS (1:1 with GCP Secret Manager)
# =========================================================================
variable "secrets" {
  description = "List of application secrets to register in Key Vault"
  type        = list(string)
  default = [
    "DB-PASSWORD",
    "DB-USER",
    "SLACK-WEBHOOK-URL",
    "SLACK-WEBHOOK-DEAD-LETTER",
    "SLACK-WEBHOOK-NEW-TABLE",
    "SLACK-WEBHOOK-JOB-COMPLETED",
    "SLACK-WEBHOOK-JOB-FAILED",
    "SLACK-WEBHOOK-QUALITY-CHECK",
    "SMTP-USER",
    "SMTP-PASSWORD"
  ]
}
