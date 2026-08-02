# Docker deployment

## Services

| Service | Image / build | Port |
|---------|---------------|------|
| frontend | `frontend/Dockerfile` (nginx) | 8080 |
| backend | `backend/Dockerfile` (FastAPI) | 8000 |
| postgres | `postgres:16-alpine` | 5432 |
| qdrant | `qdrant/qdrant:v1.13.2` | 6333 |

## Start

```bash
cp .env.example .env
docker compose up --build
```

- App: http://localhost:8080
- API docs: http://localhost:8000/docs

## Notes

- Backend entrypoint waits for Postgres, runs `alembic upgrade head`, then starts uvicorn
- Frontend nginx proxies `/api/*` to the backend service
- Document files persist in the `backend_storage` volume
- Vector data persists in `qdrant_data`
- Set real `OPENAI_API_KEY` / providers in `backend/.env.docker` for production RAG
