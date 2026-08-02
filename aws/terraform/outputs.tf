output "alb_dns_name" {
  description = "Public ALB DNS name"
  value       = aws_lb.main.dns_name
}

output "app_url" {
  description = "Application URL"
  value       = "http://${aws_lb.main.dns_name}"
}

output "api_docs_url" {
  description = "Swagger docs URL"
  value       = "http://${aws_lb.main.dns_name}/docs"
}

output "ecr_backend_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_url" {
  value = aws_ecr_repository.frontend.repository_url
}

output "s3_bucket" {
  value = aws_s3_bucket.documents.bucket
}

output "rds_endpoint" {
  value = aws_db_instance.main.address
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "secrets_arn" {
  value = aws_secretsmanager_secret.app.arn
}

output "cloudwatch_backend_log_group" {
  value = aws_cloudwatch_log_group.backend.name
}

output "cloudwatch_frontend_log_group" {
  value = aws_cloudwatch_log_group.frontend.name
}
