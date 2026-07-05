# =========================================================================
# STORAGE BUCKETS (GCS)
# =========================================================================
resource "google_storage_bucket" "frontend_bucket" {
  name          = var.frontend_bucket_name
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true
  depends_on                  = [google_project_service.enabled_apis]
}

# Make frontend bucket public-readable for hosting
resource "google_storage_bucket_iam_binding" "frontend_public" {
  bucket = google_storage_bucket.frontend_bucket.name
  role   = "roles/storage.objectViewer"
  members = [
    "allUsers"
  ]
}

resource "google_storage_bucket" "landing_bucket" {
  name          = var.landing_bucket_name
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true
  depends_on                  = [google_project_service.enabled_apis]
}

# =========================================================================
# FIRESTORE DATABASE
# =========================================================================
resource "google_firestore_database" "firestore_db" {
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
  depends_on  = [google_project_service.enabled_apis]
}

# =========================================================================
# BIGQUERY DATASETS
# =========================================================================
resource "google_bigquery_dataset" "landing_dataset" {
  dataset_id                  = "landing"
  friendly_name               = "Landing Dataset"
  description                 = "Dataset for raw ingested tables"
  location                    = var.region
  default_table_expiration_ms = 604800000 # 7 days retention
  depends_on                  = [google_project_service.enabled_apis]
}

resource "google_bigquery_dataset" "testing_dataset" {
  dataset_id    = "testing"
  friendly_name = "Testing Dataset"
  description   = "Dataset for targets and warehouse landing tables"
  location      = var.region
  depends_on    = [google_project_service.enabled_apis]
}
