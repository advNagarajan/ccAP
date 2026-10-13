# =========================================================================
# AZURE DEPLOYMENT OUTPUTS
# =========================================================================

output "resource_group_name" {
  description = "The name of the provisioned Azure Resource Group"
  value       = azurerm_resource_group.rg.name
}

output "frontend_cdn_endpoint" {
  description = "The HTTPS hostname of the Azure CDN for the frontend web app"
  value       = "https://${azurerm_cdn_endpoint.frontend_endpoint.fqdn}"
}

output "frontend_static_website_url" {
  description = "The direct storage static website primary endpoint"
  value       = azurerm_storage_account.frontend_storage.primary_web_endpoint
}

output "acr_login_server" {
  description = "The Azure Container Registry login server URI"
  value       = azurerm_container_registry.acr.login_server
}

output "postgres_fqdn" {
  description = "Fully qualified domain name of the PostgreSQL Flexible Server"
  value       = azurerm_postgresql_flexible_server.postgres.fqdn
}

output "servicebus_namespace_name" {
  description = "Name of the Azure Service Bus namespace"
  value       = azurerm_servicebus_namespace.sb.name
}

output "servicebus_connection_string" {
  description = "Primary connection string for application Service Bus integration"
  value       = azurerm_servicebus_namespace_authorization_rule.app_access.primary_connection_string
  sensitive   = true
}

output "key_vault_uri" {
  description = "The URI of the Azure Key Vault"
  value       = azurerm_key_vault.kv.vault_uri
}

output "backend_runtime_client_id" {
  description = "Client ID of the User Assigned Identity for runtime containers"
  value       = azurerm_user_assigned_identity.backend_runtime.client_id
}
