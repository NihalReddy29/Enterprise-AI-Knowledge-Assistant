############################
# S3 document storage
############################

resource "aws_s3_bucket" "documents" {
  bucket = "${local.name_prefix}-docs-${local.account_id}"
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket                  = aws_s3_bucket.documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  rule {
    id     = "abort-incomplete-uploads"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }

    filter {}
  }
}

############################
# CloudWatch log groups
############################

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${local.name_prefix}/backend"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "frontend" {
  name              = "/ecs/${local.name_prefix}/frontend"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "qdrant" {
  count             = var.qdrant_desired_count > 0 ? 1 : 0
  name              = "/ecs/${local.name_prefix}/qdrant"
  retention_in_days = 14
}

############################
# Secrets Manager
############################

resource "aws_secretsmanager_secret" "app" {
  name = "${local.name_prefix}/app"
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    SECRET_KEY         = var.secret_key
    DATABASE_URL       = "postgresql://${var.db_username}:${random_password.db.result}@${aws_db_instance.main.address}:5432/${var.db_name}"
    OPENAI_API_KEY     = var.openai_api_key
    ANTHROPIC_API_KEY  = var.anthropic_api_key
    DB_PASSWORD        = random_password.db.result
  })
}
