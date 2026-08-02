#!/usr/bin/env bash
set -euo pipefail

# Build and push backend/frontend images to ECR.
# Usage:
#   export AWS_REGION=us-east-1
#   export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
#   export PROJECT_PREFIX=enterprise-ai-assistant-production
#   ./aws/scripts/push-images.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:?Set AWS_ACCOUNT_ID}"
PROJECT_PREFIX="${PROJECT_PREFIX:?Set PROJECT_PREFIX e.g. enterprise-ai-assistant-production}"
TAG="${TAG:-latest}"

BACKEND_REPO="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${PROJECT_PREFIX}/backend"
FRONTEND_REPO="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${PROJECT_PREFIX}/frontend"

echo "Logging into ECR..."
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "Building backend..."
docker build -t "${BACKEND_REPO}:${TAG}" "$ROOT_DIR/backend"
docker push "${BACKEND_REPO}:${TAG}"

echo "Building frontend..."
docker build \
  --build-arg VITE_API_BASE_URL=/api/v1 \
  -t "${FRONTEND_REPO}:${TAG}" \
  "$ROOT_DIR/frontend"
docker push "${FRONTEND_REPO}:${TAG}"

echo "Forcing ECS redeploy..."
CLUSTER="${PROJECT_PREFIX}-cluster"
aws ecs update-service --cluster "$CLUSTER" --service "${PROJECT_PREFIX}-backend" --force-new-deployment --region "$AWS_REGION" >/dev/null
aws ecs update-service --cluster "$CLUSTER" --service "${PROJECT_PREFIX}-frontend" --force-new-deployment --region "$AWS_REGION" >/dev/null

echo "Done. Images pushed and services redeployed."
