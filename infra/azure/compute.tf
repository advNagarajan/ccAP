# =========================================================================
# COMPUTE, REGISTRY, CDN & DATABASE (Replica of GCP compute.tf)
# =========================================================================

# -------------------------------------------------------------------------
# 1. AZURE CONTAINER REGISTRY (Replaces Artifact Registry)
# -------------------------------------------------------------------------
resource "random_string" "acr_suffix" {
  length  = 4
  special = false
  upper   = false
}

resource "azurerm_container_registry" "acr" {
  name                = lower(substr("${var.acr_name}${random_string.acr_suffix.result}", 0, 50))
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "Standard"
  admin_enabled       = true

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
    Project     = var.project_name
  }
}

# -------------------------------------------------------------------------
# 2. LOG ANALYTICS & CONTAINER APPS ENVIRONMENT (Replaces Cloud Run Env)
# -------------------------------------------------------------------------
resource "azurerm_log_analytics_workspace" "logs" {
  name                = "log-${var.project_name}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_container_app_environment" "cae" {
  name                       = "cae-${var.project_name}"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.logs.id

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
    Project     = var.project_name
  }
}

# -------------------------------------------------------------------------
# 3. AZURE CDN FOR FRONTEND (Replaces Cloud CDN & HTTP Load Balancer)
# -------------------------------------------------------------------------
resource "azurerm_cdn_profile" "frontend_cdn" {
  name                = "cdn-${var.project_name}"
  location            = "global"
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "Standard_Microsoft"

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
    Project     = var.project_name
  }
}

resource "azurerm_cdn_endpoint" "frontend_endpoint" {
  name                = "fe-${lower(substr(var.project_name, 0, 15))}-${random_string.storage_suffix.result}"
  profile_name        = azurerm_cdn_profile.frontend_cdn.name
  location            = "global"
  resource_group_name = azurerm_resource_group.rg.name

  origin_host_header = azurerm_storage_account.frontend_storage.primary_web_host

  origin {
    name      = "frontend-static-origin"
    host_name = azurerm_storage_account.frontend_storage.primary_web_host
  }

  is_http_allowed  = true
  is_https_allowed = true

  delivery_rule {
    name  = "SpaRewrite"
    order = 1

    url_file_extension_condition {
      operator     = "LessThan"
      match_values = ["1"]
    }

    url_rewrite_action {
      source_pattern          = "/"
      destination             = "/index.html"
      preserve_unmatched_path = false
    }
  }
}

# -------------------------------------------------------------------------
# 4. POSTGRESQL FLEXIBLE SERVER WITH PGVECTOR (Replaces Cloud SQL)
# -------------------------------------------------------------------------
resource "azurerm_postgresql_flexible_server" "postgres" {
  name                   = var.postgres_server_name
  resource_group_name    = azurerm_resource_group.rg.name
  location               = azurerm_resource_group.rg.location
  version                = "15"
  administrator_login    = var.postgres_admin_username
  administrator_password = var.postgres_admin_password

  storage_mb   = 32768
  sku_name     = "B_Standard_B1ms" # Burstable tier for cost efficiency
  storage_tier = "P4"

  backup_retention_days = 7

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
    Project     = var.project_name
  }
}

# Allow Azure internal services (Container Apps) to access PostgreSQL
resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure_services" {
  name             = "AllowAzureServices"
  server_id        = azurerm_postgresql_flexible_server.postgres.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

# Enable pgvector extension on the Flexible Server
resource "azurerm_postgresql_flexible_server_configuration" "pgvector_config" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.postgres.id
  value     = "vector"
}

# Create metadata database
resource "azurerm_postgresql_flexible_server_database" "metadata_db" {
  name      = "metadata_db"
  server_id = azurerm_postgresql_flexible_server.postgres.id
  collation = "en_US.utf8"
  charset   = "utf8"
}
