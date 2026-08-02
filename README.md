# Enterprise AI Knowledge Assistant

SaaS-style RAG knowledge assistant with FastAPI backend and React frontend.

## Quick start (Docker)

```bash
# From repo root
cp .env.example .env
docker compose up --build
```

Services:

| Service | URL |
|---------|-----|
| Frontend | http://localhost:8080 |
| Backend API docs | http://localhost:8000/docs |
| Qdrant dashboard | http://localhost:6333/dashboard |

First registered user becomes **admin**.

### Useful commands

```bash
docker compose ps
docker compose logs -f backend
docker compose down
docker compose down -v   # also remove volumes
```

## Local development

### Backend

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5173 (proxies `/api` → backend)

## Project layout

```
enterprise-ai-assistant/
├── backend/          # FastAPI + RAG pipeline
├── frontend/         # React + Vite UI
├── docker-compose.yml
└── .env.example
```

## Phases completed

1. Auth + database
2. Document upload / OCR
3. Chunking + embeddings + vector search
4. RAG + LLM
5. Chat UI
6. Citations + PDF.js viewer
7. Admin dashboard
8. Docker deployment
9. AWS deployment (S3, RDS, ECS, CloudWatch)

## AWS deployment

See [aws/README.md](aws/README.md) for Terraform + ECR/ECS deploy steps.

```bash
cd aws/terraform
cp terraform.tfvars.example terraform.tfvars
terraform init && terraform apply
# then push images with aws/scripts/push-images.ps1
```
