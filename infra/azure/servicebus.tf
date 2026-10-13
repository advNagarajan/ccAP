# =========================================================================
# AZURE SERVICE BUS (Replica of GCP Pub/Sub Topics & Subscriptions)
# =========================================================================

# Standard SKU is required for Topics & Subscriptions (Basic only supports Queues)
resource "azurerm_servicebus_namespace" "sb" {
  name                = var.servicebus_namespace_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "Standard"

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
    Project     = var.project_name
  }
}

# -------------------------------------------------------------------------
# TOPICS
# -------------------------------------------------------------------------
resource "azurerm_servicebus_topic" "topics" {
  for_each     = toset(var.servicebus_topics)
  name         = each.key
  namespace_id = azurerm_servicebus_namespace.sb.id

  # Message retention of 7 days (ISO 8601 duration)
  default_message_ttl = "P7D"

  support_ordering = true
}

# -------------------------------------------------------------------------
# SUBSCRIPTION MAPPINGS (Identical to local.subscriptions_map in GCP)
# -------------------------------------------------------------------------
locals {
  subscriptions_map = {
    "dataset-received-sub"         = "dataset-received"
    "schema-validated-sub"         = "schema-validated"
    "metadata-extracted-sub"       = "metadata-extracted"
    "ingestion-requested-sub"      = "ingestion-requested"
    "job-failed-sub"               = "job-failed"
    "job-completed-sub"            = "job-completed"
    "drift-detected-sub"           = "drift-detected"
    "feedback-submitted-sub"       = "feedback-submitted"
    "metadata-vectorized-sub"      = "metadata-vectorized"
    "target-inferred-sub"          = "target-inferred"
    "target-mutated-sub"           = "target-mutated"
    "job-failures-dead-letter-sub" = "job-failures-dead-letter-topic"
    "quality-check-requested-sub"  = "quality-check-requested"
    "quality-check-completed-sub"  = "quality-check-completed"
    "fallback-requested-sub"       = "fallback-requested"
  }
}

resource "azurerm_servicebus_subscription" "subscriptions" {
  for_each = local.subscriptions_map
  name     = each.key
  topic_id = azurerm_servicebus_topic.topics[each.value].id

  # Lock duration 60 seconds (equivalent to GCP ack_deadline_seconds = 60)
  lock_duration = "PT1M"

  # Max deliveries before automatic dead-lettering
  max_delivery_count                 = 10
  dead_lettering_on_message_expiration = true
}

# Authorization Rule for connection strings
resource "azurerm_servicebus_namespace_authorization_rule" "app_access" {
  name         = "RootAppAccessPolicy"
  namespace_id = azurerm_servicebus_namespace.sb.id

  listen = true
  send   = true
  manage = false
}
