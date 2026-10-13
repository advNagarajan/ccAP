# =========================================================================
# MANAGED IDENTITIES & ROLE-BASED ACCESS CONTROL (RBAC)
# =========================================================================

# -------------------------------------------------------------------------
# 1. BACKEND RUNTIME MANAGED IDENTITY (Replaces backend-runtime SA)
# -------------------------------------------------------------------------
resource "azurerm_user_assigned_identity" "backend_runtime" {
  name                = "id-backend-runtime"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
    Project     = var.project_name
  }
}

# -------------------------------------------------------------------------
# 2. GITHUB DEPLOYER MANAGED IDENTITY (Replaces github-deployer SA)
# -------------------------------------------------------------------------
resource "azurerm_user_assigned_identity" "github_deployer" {
  name                = "id-github-deployer"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
    Project     = var.project_name
  }
}

# -------------------------------------------------------------------------
# 3. RBAC ROLE ASSIGNMENTS
# -------------------------------------------------------------------------

# ACR Pull for Backend Containers
resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.backend_runtime.principal_id
}

# Service Bus Data Owner for Backend & Workers
resource "azurerm_role_assignment" "servicebus_owner" {
  scope                = azurerm_servicebus_namespace.sb.id
  role_definition_name = "Azure Service Bus Data Owner"
  principal_id         = azurerm_user_assigned_identity.backend_runtime.principal_id
}

# Blob Data Contributor for Landing Storage
resource "azurerm_role_assignment" "storage_contributor" {
  scope                = azurerm_storage_account.landing_storage.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.backend_runtime.principal_id
}

# Key Vault Secrets User to read secrets at runtime
resource "azurerm_role_assignment" "keyvault_secrets_user" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.backend_runtime.principal_id
}

# Deployer permissions to push Docker images and deploy Container Apps
resource "azurerm_role_assignment" "acr_push" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPush"
  principal_id         = azurerm_user_assigned_identity.github_deployer.principal_id
}

resource "azurerm_role_assignment" "deployer_contributor" {
  scope                = azurerm_resource_group.rg.id
  role_definition_name = "Contributor"
  principal_id         = azurerm_user_assigned_identity.github_deployer.principal_id
}
