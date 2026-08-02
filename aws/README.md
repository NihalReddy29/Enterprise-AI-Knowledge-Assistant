# AWS Deployment — Enterprise AI Knowledge Assistant

Phase 9 prepares production infrastructure on AWS:

- **S3** for document storage
- **RDS PostgreSQL** for metadata
- **ECR + ECS Fargate** for Docker services
- **ALB** for HTTP routing
- **Secrets Manager** for credentials
- **CloudWatch** logs + CPU/5xx alarms
- Optional **Qdrant on ECS** (or use Qdrant Cloud / Pinecone)

## Architecture

```
Internet
   │
   ▼
Application Load Balancer
   ├─ /api/*, /docs, /health  → ECS backend (Fargate)
   └─ /*                      → ECS frontend (Fargate + nginx)
          │
          ├─ RDS PostgreSQL
          ├─ S3 documents bucket
          └─ Qdrant (ECS service discovery) / Pinecone
```

## Prerequisites

- AWS CLI configured (`aws configure`)
- Terraform >= 1.5
- Docker Desktop
- Permissions for ECR, ECS, RDS, S3, IAM, ALB, Secrets Manager, CloudWatch

## 1. Configure Terraform

```bash
cd aws/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit secret_key (openssl rand -hex 32) and API keys
```

## 2. Provision infrastructure

```bash
terraform init
terraform plan
terraform apply
```

Key outputs:

- `app_url`
- `ecr_backend_url` / `ecr_frontend_url`
- `s3_bucket`
- `rds_endpoint`
- `cloudwatch_backend_log_group`

## 3. Push Docker images

### PowerShell

```powershell
$env:AWS_REGION = "us-east-1"
$env:AWS_ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)
$env:PROJECT_PREFIX = "enterprise-ai-assistant-production"
.\aws\scripts\push-images.ps1
```

### Bash

```bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export PROJECT_PREFIX=enterprise-ai-assistant-production
./aws/scripts/push-images.sh
```

## 4. Verify

```bash
terraform output app_url
aws logs tail /ecs/enterprise-ai-assistant-production/backend --follow
curl http://$(terraform -chdir=aws/terraform output -raw alb_dns_name)/health
```

Open the ALB URL, register the first user (becomes admin), upload documents.

## Environment variables

See `aws/env/production.env.example`.

Terraform injects runtime env into the backend task definition and stores secrets in Secrets Manager:

| Variable | Source |
|----------|--------|
| `DATABASE_URL` | Secrets Manager |
| `SECRET_KEY` | Secrets Manager |
| `OPENAI_API_KEY` | Secrets Manager |
| `AWS_S3_BUCKET` | Task env |
| `STORAGE_BACKEND=s3` | Task env |
| `QDRANT_URL` | Task env (service discovery) |
| `CORS_ORIGINS` | ALB DNS |

ECS task role grants S3 read/write — no static AWS keys required in production.

## S3

Bucket is private, versioned, AES256 encrypted, with public access blocked.

App config:

```bash
STORAGE_BACKEND=s3
AWS_S3_BUCKET=<terraform output s3_bucket>
AWS_REGION=us-east-1
```

## RDS

- Engine: PostgreSQL 16
- Encrypted storage, 7-day backups
- Not publicly accessible
- Security group allows ECS tasks only

Connection string format:

```
postgresql://kaadmin:PASSWORD@RDS_ENDPOINT:5432/enterprise_ai_assistant
```

Migrations run on container start via `backend/scripts/entrypoint.sh`.

## ECS / Docker images

| Service | Image |
|---------|-------|
| backend | `{account}.dkr.ecr.{region}.amazonaws.com/{prefix}/backend:latest` |
| frontend | `{account}.dkr.ecr.{region}.amazonaws.com/{prefix}/frontend:latest` |
| qdrant | `qdrant/qdrant:v1.13.2` (public) |

ALB path routing:

- `/api/*`, `/docs`, `/redoc`, `/openapi.json`, `/health` → backend
- everything else → frontend

## CloudWatch

Log groups:

- `/ecs/{prefix}/backend`
- `/ecs/{prefix}/frontend`
- `/ecs/{prefix}/qdrant`

Alarms:

- Backend CPU > 80%
- ALB target 5xx > 5 / minute

Container Insights is enabled on the ECS cluster.

## Cost notes

Defaults use small sizes (`db.t4g.micro`, 0.25–0.5 vCPU Fargate). For production traffic, raise `db_instance_class`, CPU/memory, and desired counts in `terraform.tfvars`.

## Teardown

```bash
# Disable deletion protection first if needed
terraform destroy
```

## Optional: Pinecone instead of Qdrant

```hcl
vector_store         = "pinecone"
qdrant_desired_count = 0
```

Then add `PINECONE_API_KEY` / `PINECONE_INDEX` to Secrets Manager and the backend task definition.
