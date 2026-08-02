# Enterprise AI Knowledge Assistant - Backend

Enterprise-grade RAG Knowledge Assistant API built with FastAPI, PostgreSQL, and JWT authentication.

## Phase 1

- FastAPI project structure
- PostgreSQL + SQLAlchemy ORM
- Alembic database migrations
- JWT authentication (register, login, role-based access)
- Admin endpoints (users list, statistics)
- Rate limiting, CORS, input validation

## Phase 2

- Document upload (PDF, DOCX, PPTX, TXT, images)
- Local filesystem and AWS S3 storage backends
- Text extraction with PyMuPDF, python-docx, python-pptx
- OCR for scanned PDFs and images (Tesseract)
- Text cleaning and normalization
- Background document processing worker
- Document list, content retrieval, and delete APIs
- File validation (type, size, MIME)

## Phase 3

- Recursive character text splitter (configurable size/overlap)
- Chunk metadata: document_id, page_number, section, text
- EmbeddingService: OpenAI, Gemini, HuggingFace, Fake (local/dev)
- Vector stores: Qdrant (primary), Chroma, Pinecone, In-memory
- Indexing pipeline wired into document worker (`extracted` → `indexed`)
- Semantic search API: `POST /api/v1/search/`

## Phase 4

- Multi-provider LLM service (OpenAI, Gemini, Claude, Fake)
- Full RAG pipeline: retrieve → prompt → answer → citations
- Chat query API with conversation persistence
- Citation metadata stored on assistant messages
- Optional multi-document compare mode
- Short-term chat history injected into prompts

## Phase 6

- Document file streaming for source viewer (`GET /documents/{id}/file`)
- Citation highlight API (`GET /documents/{id}/highlight`)
- PDF.js source viewer with page jump and text highlighting
- Matching paragraph panel for cited excerpts

## Phase 7

- Admin analytics: users, documents, questions, storage, feedback
- Query logging with topic extraction
- Admin document / storage / query / feedback endpoints
- Delete users (with last-admin protection)
- Chat feedback buttons (helpful / not helpful)

## Phase 8

- Backend Dockerfile with Tesseract + Alembic entrypoint
- Frontend multi-stage Dockerfile (Vite build + nginx)
- docker-compose: frontend, backend, postgres, qdrant
- nginx reverse proxy for `/api` and SPA routing

## Phase 9 (Current)

- Terraform: S3, RDS PostgreSQL, ECR, ECS Fargate, ALB
- Secrets Manager for DATABASE_URL / JWT / API keys
- CloudWatch log groups + CPU / 5xx alarms
- Optional Qdrant ECS service with Cloud Map discovery
- Image push scripts for Windows and Linux

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── config/
│   │   └── settings.py      # Environment-based configuration
│   ├── database/
│   │   ├── base.py          # SQLAlchemy declarative base
│   │   └── session.py       # DB engine and session factory
│   ├── models/
│   │   └── user.py          # User, Document, Conversation, Message, Feedback models
│   ├── schemas/
│   │   ├── auth.py          # Auth request/response schemas
│   │   └── user.py          # User response schemas
│   ├── routers/
│   │   ├── auth.py          # /auth/register, /auth/login, /auth/me
│   │   ├── documents.py     # /documents/upload, list, delete, content
│   │   ├── search.py        # /search semantic retrieval
│   │   ├── chat.py          # Placeholder (Phase 5)
│   │   └── admin.py         # /admin/users, /admin/statistics
│   ├── services/
│   │   ├── storage.py           # Local + S3 storage backends
│   │   ├── document_processor.py # Text extraction pipeline
│   │   ├── ocr.py               # Tesseract OCR service
│   │   ├── chunking.py          # Recursive text splitter
│   │   ├── embeddings.py        # OpenAI / Gemini / HF / Fake
│   │   ├── vector_store.py      # Qdrant / Chroma / Pinecone / Memory
│   │   ├── indexing.py          # Chunk → embed → upsert orchestrator
│   │   ├── rag.py               # Phase 4
│   │   └── llm.py               # Phase 4
│   ├── workers/
│   │   └── document_worker.py   # Extract + index background task
│   └── utils/
│       ├── security.py      # Password hashing, JWT
│       ├── dependencies.py  # Auth dependencies
│       └── sanitizer.py     # Input sanitization
├── alembic/                 # Database migrations
├── tests/                   # Pytest test suite
├── requirements.txt
├── .env.example
└── alembic.ini
```

## Installation

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Tesseract OCR (optional, for scanned PDFs and images)

### Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your DATABASE_URL and SECRET_KEY

# Create PostgreSQL database
createdb enterprise_ai_assistant

# Run migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Documentation

Once running, visit:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/v1/auth/register` | Register new user | Public |
| POST | `/api/v1/auth/login` | Login, get JWT | Public |
| GET | `/api/v1/auth/me` | Current user profile | JWT |
| POST | `/api/v1/documents/upload` | Upload document | JWT |
| GET | `/api/v1/documents/` | List documents | JWT |
| GET | `/api/v1/documents/{id}` | Get document metadata | JWT |
| GET | `/api/v1/documents/{id}/content` | Get extracted text | JWT |
| GET | `/api/v1/documents/{id}/file` | Stream original file | JWT |
| GET | `/api/v1/documents/{id}/highlight` | Citation highlight spans | JWT |
| DELETE | `/api/v1/documents/{id}` | Delete document | JWT |
| POST | `/api/v1/search/` | Semantic search | JWT |
| POST | `/api/v1/chat/query` | RAG question answering | JWT |
| GET | `/api/v1/chat/conversations` | List conversations | JWT |
| GET | `/api/v1/chat/conversations/{id}` | Conversation + messages | JWT |
| DELETE | `/api/v1/chat/conversations/{id}` | Delete conversation | JWT |
| GET | `/api/v1/chat/history` | Alias for conversation list | JWT |
| GET | `/api/v1/admin/users` | List all users | Admin |
| DELETE | `/api/v1/admin/users/{id}` | Delete user | Admin |
| GET | `/api/v1/admin/documents` | List all documents | Admin |
| GET | `/api/v1/admin/storage` | Storage usage stats | Admin |
| GET | `/api/v1/admin/queries` | Recent questions | Admin |
| GET | `/api/v1/admin/feedback` | Answer feedback | Admin |
| GET | `/api/v1/admin/statistics` | Platform analytics | Admin |
| POST | `/api/v1/chat/messages/{id}/feedback` | Rate an answer | JWT |
| GET | `/health` | Health check | Public |

## Testing

```bash
pytest
```

## Database Migrations

```bash
# Create new migration after model changes
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

## Phase 3 Configuration

```bash
# Development defaults (no external services)
DEFAULT_EMBEDDING_PROVIDER=fake
VECTOR_STORE=memory

# Production example with OpenAI + Qdrant
DEFAULT_EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-...
VECTOR_STORE=qdrant
QDRANT_URL=http://localhost:6333

# Optional providers
pip install -r requirements-ai.txt   # Gemini, HuggingFace, Chroma
```

### Semantic Search Example

```bash
curl -X POST http://localhost:8000/api/v1/search/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is our leave policy?","top_k":5}'
```

Response shape:

```json
{
  "query": "What is our leave policy?",
  "total": 1,
  "results": [
    {
      "text": "Employees receive 20 paid leaves annually...",
      "document": "Employee_policy.pdf",
      "document_id": 1,
      "page_number": 12,
      "section": "Leave Policy",
      "similarity_score": 0.91
    }
  ]
}
```

## Phase 4 RAG Example

```bash
curl -X POST http://localhost:8000/api/v1/chat/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question":"What is our leave policy?","compare":false}'
```

```json
{
  "conversation_id": 1,
  "question": "What is our leave policy?",
  "answer": "Employees receive 20 paid leaves annually.",
  "citations": [
    {
      "index": 1,
      "document": "Employee_policy.pdf",
      "document_id": 1,
      "page_number": 12,
      "section": "Leave Policy",
      "similarity_score": 0.91
    }
  ],
  "provider": "fake",
  "model": "fake-rag-v1"
}
```

Set a real provider:

```bash
DEFAULT_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
# or gemini / claude (+ ANTHROPIC_API_KEY)
```

## Security Notes

- First registered user is automatically assigned **admin** role
- Passwords require uppercase, lowercase, and digit
- JWT tokens expire after 60 minutes (configurable)
- Rate limiting: 60 requests/minute per IP (configurable)
