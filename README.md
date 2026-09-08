# Enterprise AI Knowledge Assistant

SaaS-style **Retrieval-Augmented Generation (RAG)** knowledge assistant with a FastAPI backend and React frontend, for grounded, citation-backed document question-answering across large, heterogeneous document corpora.

[GitHub Repo](https://github.com/NihalReddy29/Enterprise-AI-Knowledge-Assistant)

---

## Overview

The Enterprise AI Knowledge Assistant lets users ask natural-language questions over an indexed document corpus and get answers grounded in source material, with per-source citations (document, page, similarity score) for transparency and auditability.

The project is undergoing a pipeline redesign to move from a baseline RAG setup to a more robust, agentic architecture built on **LangChain** and **LangGraph**, targeting:

- A corpus of **thousands of documents**
- **Tens of concurrent users**
- Multi-step reasoning and orchestration over retrieved context, rather than single-shot retrieval + generation

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI |
| Frontend | React (Vite) |
| Metadata storage | PostgreSQL |
| Vector storage / retrieval | Qdrant |
| Orchestration / agentic reasoning | LangChain, LangGraph |
| LLM | Google Gemini(Claude Opus, OpenAI GPT and more also works) |
| Deployment | Docker, AWS (S3, RDS, ECS, CloudWatch), Terraform |

---

## Quick Start (Docker)

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

---

## Local Development

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

---

## Project Layout
```
enterprise-ai-assistant/
├── backend/                          # FastAPI + RAG pipeline
│   ├── alembic/versions/             # DB migrations
│   ├── app/
│   │   ├── config/                   # Settings
│   │   ├── models/                   # DB models (user, org, etc.)
│   │   ├── routers/                  # API routes (chat, documents, orgs)
│   │   ├── schemas/                  # Pydantic schemas
│   │   ├── services/
│   │   │   ├── chunking.py
│   │   │   ├── embeddings.py
│   │   │   ├── indexing.py
│   │   │   ├── llm.py
│   │   │   ├── rag.py
│   │   │   ├── vector_store.py
│   │   │   ├── reranker.py           # Cross-encoder reranking
│   │   │   ├── query_processor.py
│   │   │   ├── context_validator.py
│   │   │   └── langgraph_orchestrator/  # Agentic multi-step orchestration
│   │   └── workers/                  # Background document processing
│   ├── tests/
│   └── requirements.txt
├── frontend/                         # React + Vite UI
│   └── src/
│       ├── api/                      # chat.ts, client.ts, orgs.ts
│       ├── components/               # AppLayout, MessageBubble, MarkdownAnswer
│       ├── hooks/                    # useOrgs
│       └── pages/                    # Chat, Documents, Organizations
├── docker-compose.yml
└── .env.example
```
---

## Architecture

1. **Document Processing** — Ingested documents (PDF, PPTX, etc.) are parsed and chunked.
2. **Embeddings** — Chunks are embedded and stored in Qdrant for vector-based semantic retrieval, with metadata (source, page number) tracked in PostgreSQL.
3. **Retrieval** — User queries are embedded and matched against the vector store to retrieve the most relevant chunks.
4. **Agentic Orchestration (LangGraph)** — Retrieved context is passed through a LangGraph-based flow supporting multi-step reasoning and synthesis across multiple sources, rather than relying on a single top-ranked chunk.
5. **Response Generation** — An LLM generates a grounded answer with citations back to the specific document, page, and retrieval score.

---

## Known Issues & Ongoing Improvements

Current retrieval sometimes over-weights high-level "outline" or agenda-style content (e.g., a slide listing every topic in a module) over the detailed source material that actually answers a question, since outline content can score deceptively well on plain embedding similarity. The pipeline redesign is addressing this via:

- **Hybrid retrieval** (BM25 + embeddings) to complement pure semantic search
- **Cross-encoder reranking** of top-k retrieved chunks before generation
- **Improved chunking strategy** to avoid dense, keyword-heavy outline chunks dominating retrieval
- **Multi-source synthesis** in the generation step, rather than defaulting to the single top-scored chunk

---

## Phases Completed

1. Auth + database
2. Document upload / OCR
3. Chunking + embeddings + vector search
4. RAG + LLM
5. Chat UI
6. Citations + PDF.js viewer
7. Admin dashboard
8. Docker deployment
9. AWS deployment (S3, RDS, ECS, CloudWatch)

---

## Roadmap

- [ ] Integrate hybrid (BM25 + vector) retrieval
- [ ] Add cross-encoder reranking step
- [ ] Rebuild orchestration layer with LangGraph for agentic, multi-step Q&A
- [ ] Improve chunking granularity for slide/outline-heavy documents
- [ ] Load testing for concurrent multi-user query support

---

## AWS Deployment

See [aws/README.md](aws/README.md) for Terraform + ECR/ECS deploy steps.

```bash
cd aws/terraform
cp terraform.tfvars.example terraform.tfvars
terraform init && terraform apply
# then push images with aws/scripts/push-images.ps1
```

---

