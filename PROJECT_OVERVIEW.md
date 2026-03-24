# KJV_AI - King James Version Bible Application

## Overview

KJV_AI is a full-stack Bible study application that combines traditional scripture reading with AI-powered semantic search and analytics. It uses Retrieval-Augmented Generation (RAG) to let users ask natural language questions about the Bible, backed by vector embeddings stored in ChromaDB and structured verse data in MySQL.

## Architecture

The application follows a microservices architecture, orchestrated with Docker Compose, consisting of six primary services communicating over a bridge network (`kjv_network`).

```
┌─────────────────────────────────────────────────────────┐
│                     User Browser                        │
│                          │                              │
│              ┌───────────┴───────────┐                  │
│              ▼                       ▼                  │
│     Nginx Frontend (:80)    Open WebUI (:3000)          │
│      (Angular SPA)           (Chat UI)                  │
│              │                       │                  │
│              ▼                       ▼                  │
│     Flask Webapp (:5000)    RAG API (:8001)              │
│              │                 │                         │
│              ▼                 ▼                         │
│     ┌────────┴────────┐       │                         │
│     ▼                 ▼       ▼                         │
│  MySQL (:3306)   ChromaDB (:8000)                       │
│  (verses, xrefs,  (vector embeddings)                   │
│   users, sessions)                                      │
│                                                         │
│  Analytics API (:8002) ──► MySQL                        │
│  Ollama (RunPod) ◄── Webapp / RAG API                   │
└─────────────────────────────────────────────────────────┘
```

## Services

### 1. Frontend - Nginx + Angular SPA
- **Port:** 80
- **Dockerfile:** `Dockerfile.frontend`
- **Tech:** Nginx Alpine serving a pre-built Angular 21 application
- **Config:** `nginx.conf` proxies `/api/*` requests to the Flask webapp
- **Source:** `kjv-bible-app/` directory

#### Angular App Components
| Component | Purpose |
|-----------|---------|
| `app-shell` | Main layout wrapper |
| `bible-reader` | Chapter/verse reading view |
| `bible-navigator` | Book/chapter selection sidebar |
| `chat-drawer` | AI chat interface panel |
| `search-bar` | Keyword and semantic search |
| `verse-highlight` | Verse display with cross-reference support |
| `auth-dialog` | Login/registration dialog |

#### Angular Services
| Service | Purpose |
|---------|---------|
| `bible-api.ts` | HTTP client for Flask backend API |
| `auth.service.ts` | Token-based authentication |
| `navigation.service.ts` | SPA routing and Bible navigation state |
| `reading-history.service.ts` | Reading position and history tracking |

#### Angular Dependencies
- **Angular 21** (core, router, forms, animations, CDK)
- **PrimeNG 21** - UI component library with PrimeIcons
- **RxJS** - Reactive state management
- **TypeScript 5.9**

### 2. Webapp - Flask Backend API
- **Port:** 5000
- **Dockerfile:** `Dockerfile.webapp`
- **Source:** `bible_webapp.py`
- **Server:** Gunicorn (2 workers, 120s timeout)
- **Base image:** Python 3.11-slim

#### API Endpoints
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/` | No | Serves main HTML template (legacy) |
| GET | `/api/books` | No | List all books with chapter counts |
| GET | `/api/chapter/<book>/<chapter>` | No | Get all verses in a chapter |
| GET | `/api/verse/<book>/<chapter>/<verse>` | No | Get a specific verse |
| GET | `/api/verse-by-reference/<ref>` | No | Parse and fetch by reference string |
| GET | `/api/cross-references/<book>/<ch>/<v>` | No | Get cross-references for a verse |
| POST | `/api/chat` | No | AI chat with RAG-powered responses |
| POST | `/api/search` | No | Semantic or keyword search |
| POST | `/api/auth/register` | No | Create new user account |
| POST | `/api/auth/login` | No | Authenticate and get session token |
| POST | `/api/auth/logout` | Yes | Invalidate session |
| GET | `/api/auth/me` | Yes | Get current user info |
| GET | `/api/reading/position` | Yes | Get saved reading position |
| PUT | `/api/reading/position` | Yes | Save reading position + forward stack |
| GET | `/api/reading/history` | Yes | Get reading history (back stack) |
| POST | `/api/reading/history` | Yes | Push new history entry |
| DELETE | `/api/reading/history` | Yes | Clear all history |
| GET | `/health` | No | Health check |

#### Authentication
- Token-based auth with Bearer tokens (64-char hex)
- SHA-256 password hashing with random salt
- 30-day session expiry
- MySQL-backed sessions and user tables

### 3. RAG API - FastAPI
- **Port:** 8001
- **Dockerfile:** `Dockerfile.rag`
- **Source:** `kjv_rag_api.py`
- **Server:** Uvicorn
- **Depends on:** `KJVRAGWithCrossReferences` class (from `rag_with_crossreferences.py`)

#### API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/query` | Query Bible with RAG |
| POST | `/query/stream` | Streaming query response |
| POST | `/query/batch` | Batch multiple queries |
| POST | `/v1/chat/completions` | OpenAI-compatible chat endpoint |
| GET | `/v1/models` | OpenAI-compatible models list |
| GET | `/openwebui/config` | Open WebUI integration config |
| GET | `/health` | Health check |

Runs `init_kjv_data.py` on startup to populate databases if empty.

### 4. Analytics API - FastAPI
- **Port:** 8002
- **Dockerfile:** `Dockerfile.analytics`
- **Source:** `analytics_api.py`
- **Server:** Uvicorn

#### API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/word-analysis` | Word frequency across OT/NT |
| GET | `/api/word-distribution/{word}` | Distribution scatter data |
| GET | `/api/testament-stats` | Verse/book counts by testament |
| GET | `/api/book-stats` | Per-book verse and chapter counts |
| GET | `/dashboard` | Interactive Plotly.js dashboard |
| GET | `/health` | Health check |

### 5. MySQL 8.0
- **Port:** 3306 (internal), 3307 (host)
- **Database:** `bible`
- **Volume:** `mysql_data`

#### Tables
| Table | Purpose |
|-------|---------|
| `verses` | All ~31,102 KJV verses (book, chapter, verse, text) |
| `cross_references` | Verse-to-verse cross-references with votes |
| `users` | User accounts (username, password_hash, display_name) |
| `sessions` | Auth sessions (token, user_id, expires_at) |
| `reading_history` | Per-user reading history (capped at 100 entries) |
| `reading_position` | Current reading position + forward stack (JSON) |

### 6. ChromaDB
- **Port:** 8000
- **Collection:** `kjv_bible`
- **Volume:** `chroma_data`
- **Embedding space:** Cosine similarity
- Stores vector embeddings of all Bible verses for semantic search

### 7. Open WebUI (Development Compose Only)
- **Port:** 3000 (mapped from 8080)
- **Image:** `ghcr.io/open-webui/open-webui:main`
- Connects to RAG API as an OpenAI-compatible model provider
- Connected to Ollama via RunPod for direct LLM access

## LLM Integration

- **Model:** Mistral 7B via Ollama
- **Hosted on:** RunPod (remote serverless endpoint)
- **Fallback:** If Ollama is unreachable, the webapp returns raw verse context instead of generated answers
- The RAG API exposes OpenAI-compatible endpoints so Open WebUI can treat it as a model

## Data Pipeline

### Initial Data Loading (`init_kjv_data.py`)
1. Waits for MySQL and ChromaDB to be healthy
2. Parses `KJV.txt` (tab-separated: reference + verse text)
3. Loads ~31,102 verses into MySQL `verses` table
4. Creates ChromaDB collection with cosine similarity
5. Batches verses (200 at a time) into ChromaDB with metadata

### Cross-Reference Loading
- `load_cross_references.py` - Parses `cross_references.txt`, maps abbreviations to full book names, loads into both MySQL and ChromaDB
- `load_xref_chromadb_only.py` - ChromaDB-only cross-reference loader

### Embedding Export (`kjvtensor.py`)
- Exports ChromaDB embeddings to `vectors.tsv` and `metadata.tsv` for TensorFlow Embedding Projector visualization

### Embedding Reload (`reload_all_embeddings.py`)
- Script to regenerate all embeddings from scratch

## Dependencies

### Python (requirements.txt)
| Package | Purpose |
|---------|---------|
| `chromadb` | Vector database client |
| `requests` | HTTP client for Ollama API |
| `mysql-connector-python` | MySQL database driver |
| `fastapi` | Async web framework (RAG + Analytics APIs) |
| `uvicorn[standard]` | ASGI server for FastAPI |
| `pydantic` | Data validation (FastAPI models) |
| `ollama` | Ollama Python client |
| `flask` | Web framework (main webapp) |
| `gunicorn` | WSGI server for Flask |

### Infrastructure
| Component | Version/Image | Purpose |
|-----------|---------------|---------|
| Docker Compose | v3.8 | Container orchestration |
| MySQL | 8.0 | Relational data store |
| ChromaDB | latest | Vector embedding store |
| Nginx | Alpine | Static file serving + reverse proxy |
| Python | 3.11-slim | Runtime for all Python services |
| Open WebUI | main | Chat interface (dev only) |
| Ollama/Mistral 7B | RunPod | LLM inference |

## Deployment

Two Docker Compose configurations:

### Development (`docker-compose.yml`)
- All 6 services + Open WebUI
- Exposes all ports to host
- Uses env vars from `.env`

### Production (`docker-compose.deploy.yml`)
- 4 services: MySQL, ChromaDB, Webapp, Frontend
- No exposed ports for databases (internal only)
- Frontend joins external `caddy_network` (Caddy reverse proxy)
- Stricter health checks

## File Structure

```
KJV_AI/
├── bible_webapp.py           # Flask backend (main webapp)
├── kjv_rag_api.py            # FastAPI RAG API
├── analytics_api.py          # FastAPI analytics API
├── init_kjv_data.py          # Database initialization script
├── load_cross_references.py  # Cross-reference loader (MySQL + ChromaDB)
├── load_xref_chromadb_only.py # Cross-reference loader (ChromaDB only)
├── reload_all_embeddings.py  # Embedding regeneration script
├── kjvtensor.py              # TensorFlow projector export
├── docker_init_entrypoint.py # Docker init entrypoint for RAG
├── requirements.txt          # Python dependencies
├── .env                      # Environment configuration
├── docker-compose.yml        # Development compose
├── docker-compose.deploy.yml # Production compose
├── Dockerfile.webapp         # Flask webapp image
├── Dockerfile.rag            # RAG API image
├── Dockerfile.analytics      # Analytics API image
├── Dockerfile.frontend       # Nginx + Angular image
├── nginx.conf                # Nginx reverse proxy config
├── KJV.txt                   # Full KJV Bible text (tab-separated)
├── vectors.tsv               # Exported embeddings (~295MB)
├── metadata.tsv              # Exported metadata (~4.6MB)
├── templates/
│   └── index.html            # Legacy Flask-served reader/chat UI
├── kjv_data/
│   └── KJV.txt               # Copy of Bible text for containers
├── kjv-bible-app/            # Angular 21 SPA
│   ├── src/app/
│   │   ├── components/       # UI components (reader, navigator, chat, etc.)
│   │   ├── services/         # API client, auth, navigation, history
│   │   ├── models/           # TypeScript interfaces
│   │   └── layout/           # App shell layout
│   ├── package.json          # Angular + PrimeNG dependencies
│   └── dist/                 # Built output
└── docs/                     # Documentation assets
```
