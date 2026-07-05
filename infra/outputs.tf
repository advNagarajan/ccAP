output "load_balancer_ip" {
  description = "The static public IP of the HTTP Load Balancer"
  value       = google_compute_forwarding_rule.http_forwarding_rule.ip_address
}

output "wif_provider_name" {
  description = "The Workload Identity provider ID string for GitHub Actions config"
  value       = google_iam_workload_identity_pool_provider.github_provider.name
}

output "docker_repository_uri" {
  description = "The URI of the Artifact Registry Docker repository"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_repository_name}"
}
