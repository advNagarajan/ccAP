terraform {
  required_version = ">= 1.3.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# =========================================================================
# ENABLE GOOGLE APIS
# =========================================================================
locals {
  apis = [
    "run.googleapis.com",
    "pubsub.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com",
    "aiplatform.googleapis.com",
    "firestore.googleapis.com",
    "bigquery.googleapis.com",
    "compute.googleapis.com",
    "artifactregistry.googleapis.com"
  ]
}

resource "google_project_service" "enabled_apis" {
  for_each           = toset(local.apis)
  service            = each.key
  disable_on_destroy = false
}
