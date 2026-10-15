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
# 3. AWS EC2 COMPUTE SERVER (Hosts FastAPI REST API & Continuous Worker Daemons)
# -------------------------------------------------------------------------

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_security_group" "ec2_sg" {
  name        = "${var.project_name}-ec2-sg"
  description = "Security group for Data Landing Platform API and Worker Server"

  ingress {
    description = "HTTP API access"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "FastAPI backend port"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH administrative access"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-ec2-sg"
  }
}

resource "aws_iam_role" "ec2_role" {
  name = "${var.project_name}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ec2_ecr_policy" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "ec2_s3_policy" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

resource "aws_iam_role_policy_attachment" "ec2_sqs_policy" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSQSFullAccess"
}

resource "aws_iam_role_policy_attachment" "ec2_sns_policy" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSNSFullAccess"
}

resource "aws_iam_role_policy_attachment" "ec2_ssm_policy" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2_role.name
}

resource "aws_instance" "server" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name
  vpc_security_group_ids = [aws_security_group.ec2_sg.id]

  root_block_device {
    volume_size           = 20
    volume_type           = "gp3"
    delete_on_termination = true
  }

  user_data = <<-EOF
    #!/bin/bash
    set -e

    # 1. Update system and install Docker & Git
    dnf update -y
    dnf install -y docker git
    systemctl enable docker
    systemctl start docker
    usermod -aG docker ec2-user

    # 2. Setup persistent directory and environment configuration
    mkdir -p /opt/ccap
    cat << 'ENVFILE' > /opt/ccap/.env
    CLOUD_PROVIDER=aws
    AWS_REGION=${var.aws_region}
    DB_HOST=${aws_db_instance.postgres.address}
    DB_PORT=${aws_db_instance.postgres.port}
    DB_NAME=${var.db_name}
    DB_USER=${var.db_username}
    DB_PASSWORD=${var.db_password}
    AWS_S3_LANDING_BUCKET=${aws_s3_bucket.landing_bucket.id}
    PORT=8000
    SLACK_WEBHOOK_URL=${var.slack_webhook_url}
    SLACK_WEBHOOK_JOB_COMPLETED=${var.slack_webhook_job_completed}
    SLACK_WEBHOOK_JOB_FAILED=${var.slack_webhook_job_failed}
    SLACK_WEBHOOK_QUALITY_CHECK=${var.slack_webhook_quality_check}
    SLACK_WEBHOOK_DEAD_LETTER=${var.slack_webhook_dead_letter}
    SLACK_WEBHOOK_NEW_TABLE=${var.slack_webhook_new_table}
    ENVFILE

    # 3. Pull container image from ECR and run services
    REGION=${var.aws_region}
    REPO_URL=${aws_ecr_repository.repo.repository_url}

    aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $REPO_URL || true
    docker pull $REPO_URL:latest || true

    # Run FastAPI API container on port 80 and port 8000
    docker run -d \
      --name ccap-api \
      --restart always \
      --env-file /opt/ccap/.env \
      -p 80:8000 \
      -p 8000:8000 \
      $REPO_URL:latest || true

    # Run continuous background worker supervisor
    docker run -d \
      --name ccap-workers \
      --restart always \
      --env-file /opt/ccap/.env \
      $REPO_URL:latest python scripts/run_all_workers.py || true

  EOF

  tags = {
    Name = "${var.project_name}-server"
  }
}



