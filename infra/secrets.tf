# =========================================================================
# SECRET MANAGER SECRETS (Placeholders)
# =========================================================================
resource "google_secret_manager_secret" "app_secrets" {
  for_each  = toset(var.secrets)
  secret_id = each.key

  replication {
    auto {}
  }
  depends_on = [google_project_service.enabled_apis]
}

# Grant backend runtime service account access to read secrets
resource "google_secret_manager_secret_iam_member" "sa_secret_access" {
  for_each  = toset(var.secrets)
  secret_id = google_secret_manager_secret.app_secrets[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.backend_runtime.email}"
}
