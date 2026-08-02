# Build and push images to ECR, then force ECS redeploy.
# Usage (PowerShell):
#   $env:AWS_REGION = "us-east-1"
#   $env:AWS_ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)
#   $env:PROJECT_PREFIX = "enterprise-ai-assistant-production"
#   .\aws\scripts\push-images.ps1

$ErrorActionPreference = "Stop"

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$AwsRegion = if ($env:AWS_REGION) { $env:AWS_REGION } else { "us-east-1" }
$AwsAccountId = $env:AWS_ACCOUNT_ID
$ProjectPrefix = $env:PROJECT_PREFIX
$Tag = if ($env:TAG) { $env:TAG } else { "latest" }

if (-not $AwsAccountId) { throw "Set AWS_ACCOUNT_ID" }
if (-not $ProjectPrefix) { throw "Set PROJECT_PREFIX e.g. enterprise-ai-assistant-production" }

$BackendRepo = "$AwsAccountId.dkr.ecr.$AwsRegion.amazonaws.com/$ProjectPrefix/backend"
$FrontendRepo = "$AwsAccountId.dkr.ecr.$AwsRegion.amazonaws.com/$ProjectPrefix/frontend"

Write-Host "Logging into ECR..."
aws ecr get-login-password --region $AwsRegion |
  docker login --username AWS --password-stdin "$AwsAccountId.dkr.ecr.$AwsRegion.amazonaws.com"

Write-Host "Building backend..."
docker build -t "${BackendRepo}:${Tag}" (Join-Path $RootDir "backend")
docker push "${BackendRepo}:${Tag}"

Write-Host "Building frontend..."
docker build --build-arg VITE_API_BASE_URL=/api/v1 -t "${FrontendRepo}:${Tag}" (Join-Path $RootDir "frontend")
docker push "${FrontendRepo}:${Tag}"

Write-Host "Forcing ECS redeploy..."
$Cluster = "$ProjectPrefix-cluster"
aws ecs update-service --cluster $Cluster --service "$ProjectPrefix-backend" --force-new-deployment --region $AwsRegion | Out-Null
aws ecs update-service --cluster $Cluster --service "$ProjectPrefix-frontend" --force-new-deployment --region $AwsRegion | Out-Null

Write-Host "Done. Images pushed and services redeployed."
