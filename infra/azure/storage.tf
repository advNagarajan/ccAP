# =========================================================================
# AZURE STORAGE ACCOUNTS (Replica of GCS Buckets)
# =========================================================================

# Suffix to guarantee global uniqueness for storage accounts
resource "random_string" "storage_suffix" {
  length  = 5
  special = false
  upper   = false
}

# -------------------------------------------------------------------------
# 1. RAW DATA LANDING STORAGE (Replaces GCS landing_bucket)
# -------------------------------------------------------------------------
resource "azurerm_storage_account" "landing_storage" {
  name                     = lower(substr("${var.landing_storage_name}${random_string.storage_suffix.result}", 0, 24))
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"
  is_hns_enabled           = true # Enables Azure Data Lake Storage Gen2 hierarchical namespace

  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
    Project     = var.project_name
    Role        = "LandingData"
  }
}

resource "azurerm_storage_data_lake_gen2_filesystem" "landing_filesystem" {
  name               = "landing"
  storage_account_id = azurerm_storage_account.landing_storage.id
}

# -------------------------------------------------------------------------
# 2. STATIC FRONTEND HOSTING STORAGE (Replaces GCS frontend_bucket)
# -------------------------------------------------------------------------
resource "azurerm_storage_account" "frontend_storage" {
  name                     = lower(substr("${var.frontend_storage_name}${random_string.storage_suffix.result}", 0, 24))
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"

  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = true

  static_website {
    index_document     = "index.html"
    error_404_document = "index.html"
  }

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
    Project     = var.project_name
    Role        = "FrontendHosting"
  }
}
