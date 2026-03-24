# KJV Bible RAG System - Solution Outline

## System Architecture

**5 Docker Services** running on `kjv_network`:
1. **MySQL** (port 3307) - Stores 31,102 Bible verses + cross-references
2. **ChromaDB** (port 8000) - Vector database with verse embeddings
3. **RAG API** (port 8001) - FastAPI server with RAG query endpoints
4. **Analytics** (port 8002) - Word analysis and visualization dashboard
5. **Open WebUI** (port 3000) - Chat interface for querying

## File Structure & Purpose

### Configuration Files
- **`.env`** - All environment variables (RunPod URL, MySQL password, ChromaDB settings)
- **`docker-compose.yml`** - Orchestrates all 4 services, reads from .env
- **`requirements.txt`** - Python dependencies for RAG API

### Docker Build
- **`Dockerfile.rag`** - Builds RAG API container image
- **`Dockerfile.analytics`** - Builds Analytics service container image

### Data Files
- **`KJV.txt`** - Source data: 31,102 Bible verses (tab-separated format)
- **`chroma_data/`** - ChromaDB persistent storage (14,800 embeddings)
- **`kjv_data/`** - Additional data storage directory

### Core Application Files
- **`docker_init_entrypoint.py`** - Container startup script, runs uvicorn server
- **`init_kjv_data.py`** - **[DATA LOADER]** Loads KJV.txt → MySQL + ChromaDB on startup
- **`kjv_rag_api.py`** - **[MAIN API]** FastAPI with RAG logic + OpenAI-compatible endpoints
- **`analytics_api.py`** - **[ANALYTICS]** Word analysis, statistics, and visualization API

### TensorBoard Export Files (Optional)
- **`kjvtensor.py`** - Generate TensorBoard embeddings
- **`metadata.tsv`** - TensorBoard metadata
- **`vectors.tsv`** - TensorBoard vectors

### Documentation
- **`README.md`** - Project documentation
- **`docs/`** - Additional documentation folder

## Service Dependencies

### MySQL Service
- **Supported by:** Standard MySQL 8.0 image
- **Data loaded by:** `init_kjv_data.py`
- **Tables:** `verses`, `cross_references`

### ChromaDB Service
- **Supported by:** Standard ChromaDB image
- **Data loaded by:** `init_kjv_data.py`
- **Collection:** `kjv_bible` (14,800 embeddings)

### RAG API Service
- **Built from:** `Dockerfile.rag`
- **Entrypoint:** `docker_init_entrypoint.py`
- **Main app:** `kjv_rag_api.py`
- **Data initialization:** `init_kjv_data.py` (runs on first startup)
- **Dependencies:** `requirements.txt`
- **Endpoints:**
  - `GET /` - API info
  - `GET /health` - Health check
  - `POST /query` - Traditional RAG query
  - `POST /query/stream` - Streaming response
  - `POST /query/batch` - Batch queries
  - `GET /v1/models` - OpenAI-compatible models list
  - `POST /v1/chat/completions` - OpenAI-compatible chat
  - `GET /openwebui/config` - Open WebUI configuration

### Analytics Service
- **Built from:** `Dockerfile.analytics`
- **Main app:** `analytics_api.py`
- **Dependencies:** FastAPI, uvicorn, mysql-connector-python, pydantic
- **Features:**
  - Interactive web dashboard with Plotly charts
  - Word frequency analysis (Old vs New Testament)
  - Distribution scatter plots showing verse positions
  - Testament and book-level statistics
  - Multi-word comparison charts
- **Endpoints:**
  - `GET /dashboard` - Interactive web UI
  - `POST /api/word-analysis` - Analyze multiple words
  - `GET /api/word-distribution/{word}` - Detailed distribution data
  - `GET /api/testament-stats` - Overall testament statistics
  - `GET /api/book-stats` - Per-book verse counts
  - `GET /health` - Health check

### Open WebUI Service
- **Supported by:** Official Open WebUI image
- **Connects to:** 
  - RAG API at `http://rag-api:8001/v1` (for kjv-rag model)
  - RunPod Ollama at `${OLLAMA_URL}` (for standard LLM models)
  - ChromaDB at `http://chroma:8000` (for vector storage)

## Data Flow

1. **Startup:** `docker_init_entrypoint.py` runs `init_kjv_data.py`
2. **Data Loading:** `init_kjv_data.py` reads `KJV.txt` → MySQL + ChromaDB
3. **Query Flow:**
   - User queries via Open WebUI (port 3000)
   - Open WebUI sends to RAG API `/v1/chat/completions`
   - RAG API searches ChromaDB for relevant verses
   - RAG API sends context to RunPod Ollama
   - Ollama generates answer
   - Answer returns through chain: Ollama → RAG API → Open WebUI → User

## External Dependencies
- **RunPod Ollama:** `${OLLAMA_URL}` from `.env` (requires model pulled: `mistral:7b`)

## Quick Start Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f rag-api

# Stop all services
docker-compose down

# Recreate with new config
docker-compose down && docker-compose up -d
```

## Access Points

- **Open WebUI:** http://localhost:3000
- **RAG API:** http://localhost:8001
- **RAG API Docs:** http://localhost:8001/docs
- **Analytics Dashboard:** http://localhost:8002/dashboard
- **Analytics API Docs:** http://localhost:8002/docs
- **ChromaDB:** http://localhost:8000
- **MySQL:** localhost:3307

## Troubleshooting

### Container won't pick up new .env values
```bash
# Must recreate container, restart is not enough
docker-compose down rag-api
docker-compose up -d rag-api
```

### Check if RunPod has models loaded
```bash
curl -s https://YOUR_RUNPOD_URL/api/tags
# Should show models array with mistral:7b
```

### Verify data loaded
```bash
# MySQL verse count
docker exec mysql-kjv mysql -uroot -ppassword -D bible \
  -e "SELECT COUNT(*) FROM verses;"

# ChromaDB collection
curl -s http://localhost:8000/api/v1/collections
```

## Analytics Use Cases

**Example Queries:**
- Search for "love, faith, hope" to compare their distributions
- Find where "righteousness" appears in Old vs New Testament
- Visualize the spread of "mercy" across all 66 books
- Compare "law" occurrences between testaments
- See verse position scatter plots for any word

**Charts Available:**
1. **Bar Charts** - Word counts by testament
2. **Stacked Percentage Charts** - Relative distribution
3. **Scatter Plots** - Verse position mapping
4. **Book Distribution** - Verses per book statistics

## Current Status

✅ **Working:**
- 31,102 verses loaded in MySQL
- 14,800 embeddings in ChromaDB
- RAG API endpoints functional
- Open WebUI configured with RAG API
- Analytics dashboard with interactive charts

⚠️ **Requires Setup:**
- RunPod Ollama needs model pulled (currently returns empty models list)
- Without Ollama model, RAG queries will fail with 404 error
