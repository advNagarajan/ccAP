# =========================================================================
# LOAD BALANCER & CLOUD CDN
# =========================================================================
resource "google_compute_backend_bucket" "frontend_cdn" {
  name        = "data-landing-platform-frontend"
  bucket_name = google_storage_bucket.frontend_bucket.name
  enable_cdn  = true

  cdn_policy {
    cache_mode  = "CACHE_ALL_STATIC"
    client_ttl  = 3600
    default_ttl = 3600
    max_ttl     = 86400
  }
}

resource "google_compute_url_map" "url_map" {
  name            = "data-platform-lb-url-map"
  default_service = google_compute_backend_bucket.frontend_cdn.id
}

resource "google_compute_target_http_proxy" "http_proxy" {
  name    = "data-platform-lb-target-proxy"
  url_map = google_compute_url_map.url_map.id
}

resource "google_compute_forwarding_rule" "http_forwarding_rule" {
  name                  = "data-platform-lb-forwarding-rule"
  ip_protocol           = "TCP"
  port_range            = "80"
  target                = google_compute_target_http_proxy.http_proxy.id
  load_balancing_scheme = "EXTERNAL"
}

# =========================================================================
# ARTIFACT REGISTRY
# =========================================================================
resource "google_artifact_registry_repository" "docker_repo" {
  location      = var.region
  repository_id = var.artifact_repository_name
  description   = "Docker repository for backend and worker containers"
  format        = "DOCKER"
  depends_on    = [google_project_service.enabled_apis]
}

# =========================================================================
# DATABASE (CLOUD SQL POSTGRESQL INSTANCE)
# =========================================================================
# Commented out by default to avoid accidental billing. Uncomment to provision.
/*
resource "google_sql_database_instance" "postgres_db" {
  name             = "dataset-platform-db"
  database_version = "POSTGRES_15" # Postgres 15+ compatible
  region           = var.region

  settings {
    tier = "db-f1-micro" # Lightweight development tier
    ip_configuration {
      ipv4_enabled = true
    }
  }
  deletion_protection = false
  depends_on          = [google_project_service.enabled_apis]
}

resource "google_sql_database" "database" {
  name     = "metadata_db"
  instance = google_sql_database_instance.postgres_db.name
}

resource "google_sql_user" "db_user" {
  name     = "postgres"
  instance = google_sql_database_instance.postgres_db.name
  password = "Aadhav123!" # Ideally set via Secret Manager
}
*/

