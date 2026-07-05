# =========================================================================
# PUB/SUB TOPICS & SUBSCRIPTIONS
# =========================================================================
resource "google_pubsub_topic" "topics" {
  for_each   = toset(var.pubsub_topics)
  name       = each.key
  depends_on = [google_project_service.enabled_apis]
}

# Mapping of subscription names to their target topics
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

resource "google_pubsub_subscription" "pull_subscriptions" {
  for_each = local.subscriptions_map
  name     = each.key
  topic    = google_pubsub_topic.topics[each.value].name

  # Retain messages for 7 days
  message_retention_duration = "604800s"

  # Acknowledgment deadline of 60 seconds
  ack_deadline_seconds = 60

  expiration_policy {
    # Never expire subscription due to inactivity
    ttl = ""
  }
}
