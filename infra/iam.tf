# =========================================================================
# SERVICE ACCOUNTS
# =========================================================================
resource "google_service_account" "backend_runtime" {
  account_id   = "backend-runtime"
  display_name = "Backend Services Runtime Service Account"
  depends_on   = [google_project_service.enabled_apis]
}

resource "google_service_account" "github_deployer" {
  account_id   = var.github_deployer_sa_name
  display_name = "GitHub Actions CI/CD Deployment Service Account"
  depends_on   = [google_project_service.enabled_apis]
}

resource "google_service_account" "db_agent" {
  account_id   = var.db_agent_sa_name
  display_name = "BigQuery & Firestore Data Agent Service Account"
  depends_on   = [google_project_service.enabled_apis]
}

# =========================================================================
# WORKLOAD IDENTITY FEDERATION
# =========================================================================
resource "google_iam_workload_identity_pool" "github_pool" {
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions Pool"
  description               = "Identity pool for GitHub Actions authentications"
  disabled                  = false
  depends_on                = [google_project_service.enabled_apis]
}

resource "google_iam_workload_identity_pool_provider" "github_provider" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub Actions Provider"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Allow GitHub Actions to authenticate via WIF and assume the github-deployer service account
resource "google_service_account_iam_member" "github_deployer_wif_binding" {
  service_account_id = google_service_account.github_deployer.name
  role               = "roles/iam.workloadIdentityUser"
  # Replace with principalSet referencing your specific GitHub Organization & Repository:
  # e.g., "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.repository/my-org/my-repo"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.repository/YOUR_GITHUB_ORG/YOUR_GITHUB_REPO"
}

# =========================================================================
# 4. IAM POLICY ROLES BINDINGS
# =========================================================================

# A. GitHub Deployer Permissions (to build, push, deploy, and assign the runtime SA)
locals {
  github_deployer_roles = [
    "roles/run.admin",
    "roles/artifactregistry.writer",
    "roles/storage.admin",
    "roles/iam.serviceAccountUser",
    "roles/secretmanager.secretAccessor"
  ]
}

resource "google_project_iam_member" "github_deployer_roles" {
  for_each = toset(local.github_deployer_roles)
  project  = var.project_id
  role     = each.key
  member   = "serviceAccount:${google_service_account.github_deployer.email}"
}

# B. Backend & Workers Runtime Permissions (to run Pub/Sub, Storage, SQL, BQ, Vertex AI, Firestore)
locals {
  backend_runtime_roles = [
    "roles/pubsub.publisher",
    "roles/pubsub.subscriber",
    "roles/storage.objectAdmin",
    "roles/cloudsql.client",
    "roles/aiplatform.user",
    "roles/bigquery.admin",
    "roles/datastore.user"
  ]
}

resource "google_project_iam_member" "backend_runtime_roles" {
  for_each = toset(local.backend_runtime_roles)
  project  = var.project_id
  role     = each.key
  member   = "serviceAccount:${google_service_account.backend_runtime.email}"
}

# C. Database Agent Permissions (custom credential access to Firestore and BigQuery)
locals {
  db_agent_roles = [
    "roles/bigquery.admin",
    "roles/datastore.user",
    "roles/logging.logWriter",
    "roles/pubsublite.editor",
    "roles/storage.objectAdmin"
  ]
}

resource "google_project_iam_member" "db_agent_roles" {
  for_each = toset(local.db_agent_roles)
  project  = var.project_id
  role     = each.key
  member   = "serviceAccount:${google_service_account.db_agent.email}"
}

