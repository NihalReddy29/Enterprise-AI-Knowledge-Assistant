# Enterprise AI Knowledge Assistant

SaaS-style **Retrieval-Augmented Generation (RAG)** knowledge assistant with a FastAPI backend and React frontend, for grounded, citation-backed document question-answering across large, heterogeneous document corpora.

[GitHub Repo](https://github.com/NihalReddy29/Enterprise-AI-Knowledge-Assistant)

---

## Overview

The Enterprise AI Knowledge Assistant lets users ask natural-language questions over an indexed document corpus and get answers grounded in source material, with per-source citations (document, page, similarity score) for transparency and auditability. Workspaces are **multi-tenant**: each account has a private Personal knowledge base, plus optional **Team** workspaces with isolated documents, RAG chat, and a real-time messenger.

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
│   │   ├── models/                   # DB models (user, org, team, etc.)
│   │   ├── routers/                  # API routes (chat, documents, orgs, teams)
│   │   ├── schemas/                  # Pydantic schemas
│   │   ├── services/
│   │   │   ├── chunking.py
│   │   │   ├── embeddings.py
│   │   │   ├── indexing.py
│   │   │   ├── llm.py
│   │   │   ├── rag.py
│   │   │   ├── vector_store.py
│   │   │   ├── team_collections.py   # Per-team Qdrant collections
│   │   │   ├── reranker.py           # Cross-encoder reranking
│   │   │   ├── query_processor.py
│   │   │   ├── context_validator.py
│   │   │   └── langgraph_orchestrator/  # Agentic multi-step orchestration
│   │   ├── workers/                  # Background document processing
│   │   └── ws/                       # Team messenger WebSocket
│   ├── tests/                        # Includes team isolation tests
│   └── requirements.txt
├── frontend/                         # React + Vite UI
│   └── src/
│       ├── api/                      # chat.ts, client.ts, orgs.ts, teams.ts
│       ├── components/               # AppLayout, WorkspaceSwitcher, InviteInbox
│       ├── hooks/                    # useOrgs, useTeams
│       ├── pages/                    # Chat, Documents, Teams, TeamMessenger
│       └── store/                    # workspaceStore (personal vs team)
├── docker-compose.yml
└── .env.example
```
---

## Architecture

1. **Document Processing** — Ingested documents (PDF, PPTX, etc.) are parsed and chunked.
2. **Embeddings** — Chunks are embedded and stored in Qdrant for vector-based semantic retrieval, with metadata (source, page number) tracked in PostgreSQL. Team documents land in a dedicated collection (`team_{id}`), not the personal index.
3. **Retrieval** — User queries are embedded and matched against the **active workspace** collection (personal or that team only).
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
10. **Multi-tenant Teams** — isolated workspaces (per-team Qdrant collections), email invites + join-code requests, team RAG chat, and real-time messenger

---

## Teams (multi-tenant workspaces)

Each account has a **Personal** workspace plus any **Team** workspaces they belong to. Use the header **Workspace** switcher to change context; Chat, Documents, and Messenger then read and write that workspace only. Vectors, files, and conversation history are never mixed across teams.

| Workspace | UI | Backend |
|-----------|----|---------|
| Personal | `/documents`, `/chat` | Personal uploads and conversations |
| Team | Same routes, scoped by switcher; `/messenger`, `/teams` | Isolated KB, shared RAG history, live messenger |

Messenger is team-only (disabled / empty in Personal). Team settings live at `/teams`.

### Isolation

- Each team owns a Qdrant collection named `team_{id}` and object storage under `teams/{team_id}/`.
- Membership is required for every team API; Team A cannot list, upload, RAG-chat, or message in Team B (`403`).
- Personal retrieval never searches team collections, and team RAG never searches personal (or other teams’) collections.

Covered by `backend/tests/test_teams_isolation.py`.

### Roles

| Role | Typical permissions |
|------|---------------------|
| **Owner** | Delete the team, regenerate join code, manage members and invites |
| **Admin** | Invite members, approve/reject join requests, delete any team document |
| **Member** | Upload documents, RAG chat, messenger; delete documents they uploaded |

The creator of a team is its owner.

### How people join

1. **Email invite** — Owner/admin invites by email. The invitee gets an in-app notification (Invite inbox) and an optional email with `/invites/{token}`. They must **Accept** (or reject) before they become a member. The logged-in user’s email must match the invite.
2. **Join code** — Every team has a unique join code. Anyone signed in can preview the team and **request to join**. An owner/admin must **approve** the request; membership is not granted until then. Admins can copy or regenerate the code on Team settings.

Invite emails need `FRONTEND_URL` and optional SMTP in `backend/.env` (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS`). Without SMTP, invite links still work from the in-app inbox.

### API surface (prefix `/api/v1`)

| Area | Examples |
|------|----------|
| Teams | `POST/GET /teams`, `GET /teams/{id}`, patch/delete team |
| Join | `GET /teams/join/preview?code=…`, `POST /teams/join`, admin approve/reject, regenerate join code |
| Invites | `POST /teams/{id}/invites`, `GET /teams/invites/pending`, `GET/POST /teams/invites/{token}/accept` |
| Documents | `GET /teams/{id}/documents`, `POST /teams/{id}/documents/upload` |
| RAG chat | `POST /teams/{id}/chat`, `GET /teams/{id}/conversations` |
| Messenger | `GET /teams/{id}/messages`, WebSocket `/ws/teams/{id}/messenger?token=…` |

Interactive docs: http://localhost:8000/docs (Teams, Team Documents, Team Chat, Team Messenger).

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

