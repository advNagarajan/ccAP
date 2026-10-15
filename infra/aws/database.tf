# =========================================================================
# AWS RDS POSTGRESQL DATABASE WITH PGVECTOR (Replaces Cloud SQL)
# =========================================================================

# Security Group for RDS PostgreSQL
resource "aws_security_group" "rds_sg" {
  name        = "${var.project_name}-rds-sg"
  description = "Security group allowing access to RDS PostgreSQL"

  ingress {
    description = "PostgreSQL access from anywhere"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Parameter Group enabling pgvector
resource "aws_db_parameter_group" "postgres_params" {
  name   = "${var.project_name}-pg15-params"
  family = "postgres15"

  parameter {
    name  = "rds.extensions"
    value = "vector"
  }
}

# Free-Tier eligible RDS PostgreSQL 15 Instance
resource "aws_db_instance" "postgres" {
  identifier        = "${var.project_name}-db"
  engine            = "postgres"
  engine_version    = "15.5"
  instance_class    = "db.t4g.micro" # Free-Tier eligible (or db.t3.micro)
  allocated_storage = 20
  storage_type      = "gp3"

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  parameter_group_name   = aws_db_parameter_group.postgres_params.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]

  publicly_accessible = true
  skip_final_snapshot = true
  deletion_protection = false
}
