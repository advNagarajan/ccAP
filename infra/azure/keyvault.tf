# =========================================================================
# AZURE KEY VAULT (Replica of GCP Secret Manager)
# =========================================================================

data "azurerm_client_config" "current" {}

resource "random_string" "kv_suffix" {
  length  = 4
  special = false
  upper   = false
}

resource "azurerm_key_vault" "kv" {
  name                        = lower(substr("${var.keyvault_name}${random_string.kv_suffix.result}", 0, 24))
  location                    = azurerm_resource_group.rg.location
  resource_group_name         = azurerm_resource_group.rg.name
  tenant_id                   = data.azurerm_client_config.current.tenant_id
  sku_name                    = "standard"
  soft_delete_retention_days  = 7
  purge_protection_enabled    = false
  enable_rbac_authorization   = true

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
    Project     = var.project_name
  }
}

# -------------------------------------------------------------------------
# PLACEHOLDER SECRET ENTRIES (Names converted to hyphens for Azure compliance)
# -------------------------------------------------------------------------
resource "azurerm_key_vault_secret" "app_secrets" {
  for_each     = toset(var.secrets)
  name         = replace(each.key, "_", "-")
  value        = "PLACEHOLDER_SET_IN_AZURE_PORTAL"
  key_vault_id = azurerm_key_vault.kv.id

  lifecycle {
    ignore_changes = [value] # Prevents Terraform from overwriting secrets once manually updated
  }
}
