# =========================================================================
# COMPUTE, REGISTRY & CDN (Replaces GCP Artifact Registry & Cloud CDN)
# =========================================================================

# -------------------------------------------------------------------------
# 1. AWS ELASTIC CONTAINER REGISTRY (Replaces GCP Artifact Registry)
# -------------------------------------------------------------------------
resource "aws_ecr_repository" "repo" {
  name                 = var.ecr_repository_name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# -------------------------------------------------------------------------
# 2. CLOUDFRONT CDN FOR FRONTEND (Replaces GCP Cloud CDN & Load Balancer)
# -------------------------------------------------------------------------
resource "aws_cloudfront_distribution" "frontend_cdn" {
  origin {
    domain_name = aws_s3_bucket_website_configuration.frontend_website.website_endpoint
    origin_id   = "S3FrontendOrigin"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3FrontendOrigin"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
  }

  # SPA Routing: Route 404s to index.html with HTTP 200
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

# -------------------------------------------------------------------------
# 3. AWS APP RUNNER (Replaces GCP Cloud Run for Serverless FastAPI Backend)
# -------------------------------------------------------------------------
resource "aws_iam_role" "apprunner_access_role" {
  name = "${var.project_name}-apprunner-access-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "build.apprunner.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "apprunner_ecr_policy" {
  role       = aws_iam_role.apprunner_access_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

resource "aws_iam_role" "apprunner_instance_role" {
  name = "${var.project_name}-apprunner-instance-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "tasks.apprunner.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "apprunner_s3_policy" {
  role       = aws_iam_role.apprunner_instance_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

resource "aws_iam_role_policy_attachment" "apprunner_sqs_policy" {
  role       = aws_iam_role.apprunner_instance_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSQSFullAccess"
}

resource "aws_iam_role_policy_attachment" "apprunner_sns_policy" {
  role       = aws_iam_role.apprunner_instance_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSNSFullAccess"
}

resource "aws_apprunner_service" "api_service" {
  service_name = "${var.project_name}-api"

  source_configuration {
    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_access_role.arn
    }

    image_repository {
      image_identifier      = "${aws_ecr_repository.repo.repository_url}:latest"
      image_repository_type = "ECR"

      image_configuration {
        port = "8000"
        runtime_environment_variables = {
          CLOUD_PROVIDER        = "aws"
          AWS_REGION            = var.aws_region
          DB_HOST               = aws_db_instance.postgres.address
          DB_PORT               = tostring(aws_db_instance.postgres.port)
          DB_NAME               = var.db_name
          DB_USER               = var.db_username
          DB_PASSWORD           = var.db_password
          AWS_S3_LANDING_BUCKET = aws_s3_bucket.landing_bucket.id
        }
      }
    }

    auto_deployments_enabled = true
  }

  instance_configuration {
    cpu               = "1024" # 1 vCPU
    memory            = "2048" # 2 GB RAM
    instance_role_arn = aws_iam_role.apprunner_instance_role.arn
  }

  tags = {
    Name = "${var.project_name}-api"
  }
}

