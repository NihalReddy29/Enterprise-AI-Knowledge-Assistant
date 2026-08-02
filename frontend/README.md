# Knowledge Assistant — Frontend

React + Vite + TypeScript UI for the Enterprise AI Knowledge Assistant.

## Stack

- React 19 + Vite
- TypeScript
- Tailwind CSS v4
- React Query
- Axios
- Zustand
- React Router

## Pages

- `/login` — Sign in / register
- `/` — Dashboard
- `/documents` — Upload and manage documents
- `/chat` — Conversations, RAG Q&A, clickable citations
- `/admin` — Admin stats and users (admin role only)

## Citations / Source viewer (Phase 6)

Clicking a citation opens a modal that:

1. Loads the original file (`GET /documents/{id}/file`)
2. Fetches highlight metadata (`GET /documents/{id}/highlight`)
3. For PDFs, renders the cited page with PDF.js and highlights matching text
4. Shows the matching paragraph with yellow marks for non-PDF too

## Setup

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

App: http://localhost:5173  
API proxy: `/api` → `http://localhost:8000`

## Scripts

```bash
npm run dev
npm run build
npm run preview
```
