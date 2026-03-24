#!/usr/bin/env python3
"""
Docker entrypoint script that initializes data and starts the RAG API.
"""

import subprocess
import sys
import os

def run_init():
    """Run the data initialization script."""
    print("=" * 60)
    print("KJV RAG API - Docker Init Entrypoint")
    print("=" * 60)
    
    # Run initialization
    print("\n🔄 Running data initialization...")
    try:
        result = subprocess.run(
            [sys.executable, "/app/init_kjv_data.py"],
            capture_output=False,
            text=True,
            timeout=600  # 10 minute timeout
        )
        if result.returncode != 0:
            print(f"⚠️  Initialization returned code {result.returncode}")
    except subprocess.TimeoutExpired:
        print("⚠️  Initialization timed out after 10 minutes")
    except Exception as e:
        print(f"⚠️  Initialization error: {e}")
    
    print("\n🚀 Starting RAG API...")
    # Start the RAG API
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "kjv_rag_api:app",
        "--host", "0.0.0.0",
        "--port", "8001"
    ])

if __name__ == "__main__":
    run_init()
