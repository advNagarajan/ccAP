# =========================================================================
# AWS MESSAGING: SNS TOPICS & SQS QUEUES (Replaces GCP Pub/Sub)
# =========================================================================

# -------------------------------------------------------------------------
# 1. SNS TOPICS (Replaces GCP Pub/Sub Topics)
# -------------------------------------------------------------------------
resource "aws_sns_topic" "topics" {
  for_each = toset(var.topics)
  name     = each.key
}

# -------------------------------------------------------------------------
# 2. SQS QUEUES (Replaces GCP Pub/Sub Pull Subscriptions)
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

resource "aws_sqs_queue" "queues" {
  for_each                   = local.subscriptions_map
  name                       = each.key
  message_retention_seconds = 604800 # 7 days retention
  visibility_timeout_seconds = 60     # 60s processing window (matches GCP ack_deadline = 60)
  receive_wait_time_seconds  = 10     # Long-polling enabled
}

# -------------------------------------------------------------------------
# 3. SUBSCRIBE SQS QUEUES TO SNS TOPICS
# -------------------------------------------------------------------------
resource "aws_sns_topic_subscription" "sns_to_sqs" {
  for_each  = local.subscriptions_map
  topic_arn = aws_sns_topic.topics[each.value].arn
  protocol  = "sqs"
  endpoint  = aws_sqs_queue.queues[each.key].arn

  raw_message_delivery = false
}

# -------------------------------------------------------------------------
# 4. SQS QUEUE ACCESS POLICIES (Allows SNS to deliver messages to SQS)
# -------------------------------------------------------------------------
resource "aws_sqs_queue_policy" "queue_policy" {
  for_each  = local.subscriptions_map
  queue_url = aws_sqs_queue.queues[each.key].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowSNSPublish"
        Effect    = "Allow"
        Principal = "*"
        Action    = "sqs:SendMessage"
        Resource  = aws_sqs_queue.queues[each.key].arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_sns_topic.topics[each.value].arn
          }
        }
      }
    ]
  })
}
