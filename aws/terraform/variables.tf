variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name prefix for resources"
  type        = string
  default     = "enterprise-ai-assistant"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "production"
}

variable "vpc_id" {
  description = "Existing VPC ID (uses default VPC when empty)"
  type        = string
  default     = ""
}

variable "public_subnet_ids" {
  description = "Public subnet IDs for ALB/ECS (auto-detected from VPC when empty)"
  type        = list(string)
  default     = []
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for RDS (falls back to public subnets when empty)"
  type        = list(string)
  default     = []
}

variable "db_username" {
  description = "RDS master username"
  type        = string
  default     = "kaadmin"
}

variable "db_name" {
  description = "Application database name"
  type        = string
  default     = "enterprise_ai_assistant"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "backend_cpu" {
  type    = number
  default = 512
}

variable "backend_memory" {
  type    = number
  default = 1024
}

variable "frontend_cpu" {
  type    = number
  default = 256
}

variable "frontend_memory" {
  type    = number
  default = 512
}

variable "backend_desired_count" {
  type    = number
  default = 1
}

variable "frontend_desired_count" {
  type    = number
  default = 1
}

variable "qdrant_desired_count" {
  description = "Set 0 to skip self-hosted Qdrant (use Qdrant Cloud / Pinecone instead)"
  type        = number
  default     = 1
}

variable "secret_key" {
  description = "JWT SECRET_KEY for the API"
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "Optional OpenAI API key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "anthropic_api_key" {
  description = "Optional Anthropic API key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "default_llm_provider" {
  type    = string
  default = "openai"
}

variable "default_embedding_provider" {
  type    = string
  default = "openai"
}

variable "vector_store" {
  description = "qdrant | pinecone | memory"
  type        = string
  default     = "qdrant"
}

variable "domain_name" {
  description = "Optional custom domain for future ACM/HTTPS setup"
  type        = string
  default     = ""
}
