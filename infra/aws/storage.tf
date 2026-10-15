# =========================================================================
# AWS S3 STORAGE BUCKETS (Replaces GCS Buckets)
# =========================================================================

resource "random_string" "bucket_suffix" {
  length  = 6
  special = false
  upper   = false
}

# -------------------------------------------------------------------------
# 1. RAW DATA LANDING S3 BUCKET (Replaces GCS landing_bucket)
# -------------------------------------------------------------------------
resource "aws_s3_bucket" "landing_bucket" {
  bucket        = "${var.landing_bucket_prefix}-${random_string.bucket_suffix.result}"
  force_destroy = false
}

resource "aws_s3_bucket_versioning" "landing_versioning" {
  bucket = aws_s3_bucket.landing_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "landing_encryption" {
  bucket = aws_s3_bucket.landing_bucket.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# -------------------------------------------------------------------------
# 2. STATIC FRONTEND HOSTING S3 BUCKET (Replaces GCS frontend_bucket)
# -------------------------------------------------------------------------
resource "aws_s3_bucket" "frontend_bucket" {
  bucket        = "${var.frontend_bucket_prefix}-${random_string.bucket_suffix.result}"
  force_destroy = true
}

resource "aws_s3_bucket_website_configuration" "frontend_website" {
  bucket = aws_s3_bucket.frontend_bucket.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "index.html"
  }
}

resource "aws_s3_bucket_public_access_block" "frontend_public_access" {
  bucket = aws_s3_bucket.frontend_bucket.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "frontend_public_read" {
  bucket     = aws_s3_bucket.frontend_bucket.id
  depends_on = [aws_s3_bucket_public_access_block.frontend_public_access]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.frontend_bucket.arn}/*"
      }
    ]
  })
}
