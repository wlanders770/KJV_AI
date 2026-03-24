# KJV Bible AI — Architecture Document

## System Overview

A full-stack Bible study application combining traditional scripture reading with AI-powered semantic search, cross-reference exploration, and natural language chat. Built as a Docker microservices architecture with an Angular 21 SPA frontend.

**Production URL:** `https://bible.intagent.ai`

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Layer                         │
│  ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Angular 21 SPA  │  │  Open WebUI  │  │  Claude MCP  │  │
│  │  (PrimeNG UI)    │  │  :3000       │  │  Server      │  │
│  └────────┬─────────┘  └──────┬───────┘  └──────┬───────┘  │
└───────────┼────────────────────┼─────────────────┼──────────┘
            │                    │                 │
┌───────────▼────────────────────▼─────────────────▼──────────┐
│                    Nginx Reverse Proxy :80                   │
│         /api/* → webapp    /rag/* → rag-api                 │
│         /analytics/* → analytics    /* → SPA                │
└───────────┬────────────────────┬─────────────────┬──────────┘
            │                    │                 │
┌───────────▼──────┐  ┌─────────▼───────┐  ┌──────▼─────────┐
│  Flask Webapp    │  │  RAG API        │  │  Analytics API │
│  :5000           │  │  FastAPI :8001  │  │  FastAPI :8002 │
│                  │  │                 │  │                │
│  - Auth (users)  │  │  - Semantic Q&A │  │  - Word freq   │
│  - Bible CRUD    │  │  - LLM chat     │  │  - Book stats  │
│  - Search        │  │  - Streaming    │  │  - Plotly dash │
│  - Cross-refs    │  │  - OpenAI compat│  │                │
│  - Reading hist  │  │                 │  │                │
└────────┬─────────┘  └───┬─────┬───────┘  └───────┬────────┘
         │                │     │                   │
    ┌────▼────────────────▼─┐ ┌─▼───────────┐ ┌────▼────┐
    │     MySQL :3306       │ │ ChromaDB    │ │ Ollama  │
    │                       │ │ :8000       │ │ RunPod  │
    │  - verses (31,102)    │ │             │ │ GPU     │
    │  - cross_references   │ │  ~14,800    │ │         │
    │  - users / sessions   │ │  embeddings │ │ mistral │
    │  - reading_history    │ │             │ │ :7b     │
    │  - reading_position   │ │             │ │         │
    └───────────────────────┘ └─────────────┘ └─────────┘
```

---

## Service Details

### 1. Angular Frontend (`kjv-bible-app/`)

**Stack:** Angular 21, PrimeNG 21, RxJS 7.8, TypeScript 5.9

| Component | Purpose |
|-----------|---------|
| `AppShell` | Main layout — toolbar, sidebar drawers |
| `BibleReader` | Virtual-scroll chapter/verse viewer |
| `BibleNavigator` | Book/chapter/verse picker with search |
| `SearchBar` | Semantic + keyword search with results |
| `ChatDrawer` | Side-panel AI chat interface |
| `AuthDialog` | Login/registration modal |
| `VerseHighlight` | Verse display with cross-reference links |

**Services:**
- `BibleApiService` — HTTP client for all `/api/*` endpoints
- `AuthService` — Bearer token auth, localStorage persistence
- `NavigationService` — Reactive signals for current book/chapter/verse
- `ReadingHistoryService` — Back/forward navigation, server sync

**Build:** `ng build` → `kjv-bible-app/dist/` → served by Nginx

---

### 2. Flask Webapp (`bible_webapp.py`) — Port 5000

**Role:** Primary API gateway for the Angular frontend.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/books` | List all 66 books |
| GET | `/api/chapter/{book}/{ch}` | All verses in a chapter |
| GET | `/api/verse/{book}/{ch}/{v}` | Single verse |
| GET | `/api/verse-by-reference/{ref}` | Lookup by reference string |
| POST | `/api/search` | Semantic (ChromaDB) + keyword (MySQL) search |
| POST | `/api/chat` | RAG-augmented chat via Ollama |
| GET | `/api/cross-references/{book}/{ch}/{v}` | Cross-reference lookup |
| POST | `/api/auth/register` | User registration (SHA-256+salt) |
| POST | `/api/auth/login` | User login |
| GET | `/api/auth/me` | Current user info |
| POST | `/api/auth/logout` | Session invalidation |
| GET/PUT | `/api/reading/position` | Reading position persistence |
| GET/POST/DELETE | `/api/reading/history` | Reading history CRUD |

**Dependencies:** MySQL, ChromaDB, Ollama (via env vars)

---

### 3. RAG API (`kjv_rag_api.py`) — Port 8001

**Role:** Semantic search and LLM-augmented Bible Q&A.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/query` | RAG query with optional cross-references |
| POST | `/query/stream` | Streaming RAG response |
| POST | `/query/batch` | Batch multiple queries |
| POST | `/v1/chat/completions` | OpenAI-compatible (Open WebUI) |
| GET | `/v1/models` | OpenAI models list |

**Startup:** Runs `init_kjv_data.py` to ensure MySQL + ChromaDB are populated.

**Dependencies:** MySQL, ChromaDB, Ollama, `rag_with_crossreferences` module

---

### 4. Analytics API (`analytics_api.py`) — Port 8002

**Role:** Word frequency analysis and statistical visualization.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/word-analysis` | Word frequency across OT/NT |
| GET | `/api/word-distribution/{word}` | Scatter data for visualization |
| GET | `/api/testament-stats` | Overall verse/book counts |
| GET | `/api/book-stats` | Per-book statistics |
| GET | `/dashboard` | Embedded Plotly.js dashboard |

**Dependencies:** MySQL only

---

### 5. MCP Server (`kjv_mcp_server.py`)

**Role:** Exposes Bible APIs as Claude Model Context Protocol tools.

**Tools Exposed:**
- Reading: `get_books()`, `get_chapter()`, `get_verse()`, `get_verse_by_reference()`
- Search: `search_bible()`, `get_cross_references()`
- Chat: `chat_with_bible()`, `rag_query()`
- Analytics: `word_analysis()`, `word_distribution()`, `testament_stats()`, `book_stats()`

**Dependencies:** Calls Flask Webapp, RAG API, and Analytics API over HTTP

---

### 6. Data Initialization (`init_kjv_data.py`)

**Role:** One-time setup — parses `KJV.txt` and populates MySQL + ChromaDB.

**Sequence:**
1. Wait for MySQL health → create `verses` + `cross_references` tables → bulk insert 31,102 verses
2. Wait for ChromaDB health → create `kjv_bible` collection → batch-add embeddings (200/batch)

**Triggered by:** `docker_init_entrypoint.py` on RAG container startup

---

## Data Layer

### MySQL Tables

| Table | Columns | Records |
|-------|---------|---------|
| `verses` | book, chapter, verse, text | 31,102 |
| `cross_references` | from_book, from_chapter, from_verse, to_reference, votes | variable |
| `users` | id, username, password_hash, salt, created_at | per-user |
| `sessions` | token, user_id, created_at, expires_at | per-session |
| `reading_position` | user_id, book, chapter, verse, forward_stack | per-user |
| `reading_history` | user_id, book, chapter, verse, timestamp | per-visit |

### ChromaDB Collections

| Collection | Documents | Purpose |
|------------|-----------|---------|
| `kjv_bible` | ~14,800 embeddings | Semantic verse search |

### Source Data

| File | Size | Format |
|------|------|--------|
| `KJV.txt` | 4.4 MB | Tab-separated: `reference\ttext` (31,102 lines) |

---

## Deployment

### Development (`docker-compose.yml`)

Services: mysql, chroma, rag-api, analytics, webapp, open-webui
Network: `kjv_network` (bridge)
Ports exposed: 3307 (MySQL), 5000 (Flask), 8000 (ChromaDB), 8001 (RAG), 8002 (Analytics), 3000 (Open WebUI)

### Production (`docker-compose.deploy.yml`)

Services: webapp, rag-api, analytics, mysql, chroma, frontend
Network: `caddy_network` (external — Caddy reverse proxy handles TLS)
No ports exposed directly — all traffic via Caddy → Nginx → services

---

## Environment Variables (`.env`)

| Variable | Purpose | Default |
|----------|---------|---------|
| `OLLAMA_URL` | RunPod GPU endpoint for LLM inference | RunPod proxy URL |
| `OLLAMA_MODEL` | LLM model name | `mistral:7b` |
| `CHROMA_HOST` | ChromaDB hostname | `chroma` |
| `CHROMA_PORT` | ChromaDB port | `8000` |
| `MYSQL_HOST` | MySQL hostname | `mysql` |
| `MYSQL_PORT` | MySQL port | `3306` |
| `MYSQL_USER` | MySQL username | `root` |
| `MYSQL_PASSWORD` | MySQL password | (set in .env) |
| `MYSQL_DATABASE` | MySQL database name | `bible` |

---

## Utility Scripts

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `load_cross_references.py` | Load cross-refs from text file → MySQL + ChromaDB | Initial cross-reference data load |
| `load_xref_chromadb_only.py` | Sync MySQL cross-refs → ChromaDB embeddings | When ChromaDB needs re-sync |
| `reload_all_embeddings.py` | Delete + recreate entire ChromaDB collection | Full embedding rebuild |

---

## File Inventory

### Active Source Files
```
bible_webapp.py              Flask API gateway
analytics_api.py             Word analytics FastAPI service
kjv_rag_api.py               RAG query FastAPI service
init_kjv_data.py             Data initialization script
docker_init_entrypoint.py    Docker container entrypoint
kjv_mcp_server.py            Claude MCP server
load_cross_references.py     Cross-reference loader (utility)
load_xref_chromadb_only.py   ChromaDB-only xref loader (utility)
reload_all_embeddings.py     Embedding rebuild script (utility)
requirements.txt             Python dependencies
```

### Docker/Deployment
```
Dockerfile.webapp            Flask container
Dockerfile.rag               RAG API container
Dockerfile.analytics         Analytics container
Dockerfile.frontend          Nginx + Angular container
docker-compose.yml           Development orchestration
docker-compose.deploy.yml    Production orchestration
nginx.conf                   Nginx reverse proxy config
.env                         Environment configuration
```

### Frontend
```
kjv-bible-app/               Angular 21 SPA (PrimeNG)
```

### Data
```
KJV.txt                      Source Bible text (31,102 verses)
```

---

## Known Issues

1. **Missing `rag_with_crossreferences.py`** — The RAG API imports `KJVRAGWithCrossReferences` from this module, but it does not exist in the repository. The RAG service cannot start without it.
2. **No `.gitignore`** — `__pycache__/`, `node_modules/`, `.env`, and build artifacts are not excluded.
3. **Most source files are untracked in git** — Only `vectors.tsv`, `metadata.tsv`, `.gitattributes`, and `README.md` are committed.
