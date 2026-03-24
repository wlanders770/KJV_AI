"""
FastAPI Server for KJV RAG with Cross-References
================================================
Exposes the RAG system as a REST API that Open WebUI can call.

Installation:
    pip install fastapi uvicorn chromadb requests mysql-connector-python

Run:
    uvicorn kjv_rag_api:app --reload --host 0.0.0.0 --port 8001
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import json
import logging
import subprocess
import sys
from pathlib import Path
import time

# Import the RAG system
from rag_with_crossreferences import KJVRAGWithCrossReferences

# ========== LOGGING ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== FASTAPI APP ==========
app = FastAPI(
    title="KJV Bible RAG API",
    description="Query KJV Bible verses with cross-references using RAG",
    version="1.0.0"
)

# ========== MODELS ==========
class QueryRequest(BaseModel):
    query: str
    include_references: bool = True
    model: Optional[str] = None  # Allow overriding model

class QueryResponse(BaseModel):
    query: str
    answer: str
    context: str
    include_references: bool

# OpenAI-compatible models
class ChatMessage(BaseModel):
    role: str  # "user", "assistant", "system"
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.3
    max_tokens: Optional[int] = 200
    top_p: Optional[float] = 0.9

class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"

class ChatCompletionResponse(BaseModel):
    id: str = "kjv-rag-1"
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: dict = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

# ========== INITIALIZE RAG ==========
rag_system = None

@app.on_event("startup")
async def startup_event():
    """Initialize data and RAG system on startup."""
    global rag_system
    
    # Run data initialization if needed
    init_script = Path("/app/init_kjv_data.py")
    if init_script.exists():
        logger.info("🔄 Running database initialization...")
        try:
            result = subprocess.run(
                [sys.executable, str(init_script)],
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
            for line in result.stdout.split('\n'):
                if line.strip():
                    logger.info(f"  {line}")
            if result.returncode != 0:
                logger.warning(f"⚠️  Initialization returned code {result.returncode}")
                if result.stderr:
                    logger.warning(f"  Error: {result.stderr}")
        except subprocess.TimeoutExpired:
            logger.warning("⚠️  Data initialization timed out after 10 minutes")
        except Exception as e:
            logger.warning(f"⚠️  Data initialization error: {e}")
    
    # Initialize RAG system
    try:
        rag_system = KJVRAGWithCrossReferences()
        logger.info("✅ RAG system initialized successfully")
    except Exception as e:
        logger.warning(f"⚠️  Failed to fully initialize RAG system: {e}")
        logger.info("   This is OK if it's a missing collection - will initialize on first query")
        # Don't raise - allow the API to start even if collections don't exist yet
        # They will be created/populated on demand

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections on shutdown."""
    global rag_system
    if rag_system:
        rag_system.close()
        logger.info("🔌 RAG system shutdown")

# ========== ROUTES ==========

@app.get("/")
async def root():
    """Health check and API info."""
    return {
        "status": "online",
        "service": "KJV Bible RAG with Cross-References",
        "endpoints": [
            "/docs - Interactive API documentation (Swagger UI)",
            "/query - POST: Query the Bible",
            "/health - GET: Health check",
        ]
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "rag_system": "ready" if rag_system else "not initialized"
    }

@app.post("/query", response_model=QueryResponse)
async def query_bible(request: QueryRequest):
    """
    Query the KJV Bible with optional cross-references.
    
    Args:
        query: Bible-related question or search term
        include_references: Include cross-references in context
        
    Returns:
        Query result with answer and context
    """
    if not rag_system:
        raise HTTPException(status_code=503, detail="RAG system not initialized")
    
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    try:
        logger.info(f"Processing query: {request.query[:50]}...")
        
        # Get answer from RAG system
        result = rag_system.ask(
            request.query,
            include_references=request.include_references
        )
        
        return QueryResponse(
            query=result['query'],
            answer=result['answer'],
            context=result['context'][:2000],  # Truncate context for response
            include_references=request.include_references
        )
    
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/query/stream")
async def query_bible_stream(request: QueryRequest):
    """
    Stream query results (for real-time responses).
    """
    if not rag_system:
        raise HTTPException(status_code=503, detail="RAG system not initialized")
    
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    try:
        result = rag_system.ask(
            request.query,
            include_references=request.include_references
        )
        
        # Return streaming response
        return JSONResponse(content=result)
    
    except Exception as e:
        logger.error(f"Error in stream query: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/query/batch", response_model=List[QueryResponse])
async def query_batch(requests_list: List[QueryRequest]):
    """
    Process multiple queries at once.
    
    Args:
        requests_list: List of query requests
        
    Returns:
        List of query responses
    """
    if not rag_system:
        raise HTTPException(status_code=503, detail="RAG system not initialized")
    
    results = []
    
    for req in requests_list:
        try:
            result = rag_system.ask(
                req.query,
                include_references=req.include_references
            )
            
            results.append(QueryResponse(
                query=result['query'],
                answer=result['answer'],
                context=result['context'][:2000],
                include_references=req.include_references
            ))
        except Exception as e:
            logger.error(f"Error in batch query: {e}")
            # Continue with other queries
            results.append(QueryResponse(
                query=req.query,
                answer=f"Error: {str(e)}",
                context="",
                include_references=req.include_references
            ))
    
    return results

@app.get("/openwebui/config")
async def openwebui_config():
    """
    Returns configuration for Open WebUI integration.
    Add this as a custom tool in Open WebUI.
    """
    return {
        "name": "KJV Bible RAG",
        "description": "Query the KJV Bible with cross-references",
        "endpoint": "http://localhost:8001/query",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json"
        },
        "parameters": {
            "query": {
                "type": "string",
                "description": "Your Bible question or search term"
            },
            "include_references": {
                "type": "boolean",
                "description": "Include cross-references",
                "default": True
            }
        }
    }

@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    """
    OpenAI-compatible chat completions endpoint.
    Allows Open WebUI to use this RAG API as a model provider.
    
    This endpoint:
    1. Extracts the user query from messages
    2. Uses RAG system to retrieve Bible verses
    3. Returns results in OpenAI format
    """
    if not rag_system:
        raise HTTPException(status_code=503, detail="RAG system not initialized")
    
    try:
        # Extract user message (last message from user)
        user_query = None
        for message in reversed(request.messages):
            if message.role == "user":
                user_query = message.content
                break
        
        if not user_query:
            raise HTTPException(status_code=400, detail="No user message found")
        
        logger.info(f"Chat completion request: {user_query[:50]}...")
        
        # Get RAG answer
        result = rag_system.ask(
            user_query,
            include_references=True,
            top_k=5
        )
        
        # Return in OpenAI format
        return ChatCompletionResponse(
            model=request.model or "kjv-rag",
            created=int(time.time()),
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=result['answer']
                    ),
                    finish_reason="stop"
                )
            ],
            usage={
                "prompt_tokens": len(user_query.split()),
                "completion_tokens": len(result['answer'].split()),
                "total_tokens": len(user_query.split()) + len(result['answer'].split())
            }
        )
    
    except Exception as e:
        logger.error(f"Error in chat completions: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/v1/models")
async def list_models():
    """
    OpenAI-compatible models endpoint.
    Returns available models for Open WebUI.
    """
    return {
        "object": "list",
        "data": [
            {
                "id": "kjv-rag",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "kjv-bible-rag",
                "permission": [],
                "root": "kjv-rag",
                "parent": None
            }
        ]
    }

# ========== ERROR HANDLERS ==========

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
