#!/usr/bin/env python3
"""
MCP Server for KJV Bible API
Exposes Bible reading, search, RAG queries, and analytics as MCP tools.
Proxies requests to the existing Flask (webapp) and FastAPI (rag, analytics) services.
"""

import json
import os
import sys
import logging
from typing import Any

import requests
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("kjv-mcp")

# Service base URLs
# When using the reverse proxy (production), all services go through one host:
#   KJV_WEBAPP_URL=https://bible.intagent.ai       (webapp at /api/*)
#   KJV_RAG_URL=https://bible.intagent.ai/rag       (rag at /rag/*)
#   KJV_ANALYTICS_URL=https://bible.intagent.ai/analytics  (analytics at /analytics/*)
# When using direct Docker ports (dev), use separate ports:
#   KJV_WEBAPP_URL=http://localhost:5000
#   KJV_RAG_URL=http://localhost:8001
#   KJV_ANALYTICS_URL=http://localhost:8002
WEBAPP_URL = os.getenv("KJV_WEBAPP_URL", "https://bible.intagent.ai")
RAG_URL = os.getenv("KJV_RAG_URL", "https://bible.intagent.ai/rag")
ANALYTICS_URL = os.getenv("KJV_ANALYTICS_URL", "https://bible.intagent.ai/analytics")

mcp = FastMCP(
    "KJV Bible",
    instructions="Read, search, and analyze the King James Version Bible",
)


def _get(url: str, **kwargs) -> dict:
    """GET helper with error handling."""
    resp = requests.get(url, timeout=30, **kwargs)
    resp.raise_for_status()
    return resp.json()


def _post(url: str, payload: dict, **kwargs) -> dict:
    """POST helper with error handling."""
    resp = requests.post(url, json=payload, timeout=60, **kwargs)
    resp.raise_for_status()
    return resp.json()


# ============================================
# Bible Reading Tools
# ============================================

@mcp.tool()
def get_books() -> str:
    """List all 66 books of the Bible with their chapter counts."""
    data = _get(f"{WEBAPP_URL}/api/books")
    books = data["books"]
    lines = []
    for b in books:
        lines.append(f"{b['name']} ({b['chapters']} chapters)")
    return "\n".join(lines)


@mcp.tool()
def get_chapter(book: str, chapter: int) -> str:
    """Get all verses in a chapter.

    Args:
        book: Book name (e.g. "Genesis", "1 Corinthians")
        chapter: Chapter number
    """
    data = _get(f"{WEBAPP_URL}/api/chapter/{book}/{chapter}")
    verses = data.get("verses", [])
    if not verses:
        return f"No verses found for {book} {chapter}"
    lines = []
    for v in verses:
        lines.append(f"{v['book']} {v['chapter']}:{v['verse']}  {v['text']}")
    return "\n".join(lines)


@mcp.tool()
def get_verse(book: str, chapter: int, verse: int) -> str:
    """Get a single verse by book, chapter, and verse number.

    Args:
        book: Book name (e.g. "John")
        chapter: Chapter number
        verse: Verse number
    """
    data = _get(f"{WEBAPP_URL}/api/verse/{book}/{chapter}/{verse}")
    v = data.get("verse")
    if not v:
        return f"Verse not found: {book} {chapter}:{verse}"
    return f"{v['book']} {v['chapter']}:{v['verse']}  {v['text']}"


@mcp.tool()
def get_verse_by_reference(reference: str) -> str:
    """Look up a verse by its reference string. Supports ranges.

    Args:
        reference: e.g. "John 3:16" or "Genesis 1:1-5"
    """
    data = _get(f"{WEBAPP_URL}/api/verse-by-reference/{reference}")
    verses = data.get("verses", [])
    if not verses:
        return f"Not found: {reference}"
    lines = []
    for v in verses:
        lines.append(f"{v['book']} {v['chapter']}:{v['verse']}  {v['text']}")
    return "\n".join(lines)


# ============================================
# Search Tools
# ============================================

@mcp.tool()
def search_bible(query: str, search_type: str = "semantic") -> str:
    """Search the Bible using semantic (AI meaning) or keyword (exact text) search.

    Args:
        query: What to search for
        search_type: "semantic" for meaning-based search, "keyword" for exact text match
    """
    data = _post(f"{WEBAPP_URL}/api/search", {
        "query": query,
        "type": search_type,
    })
    verses = data.get("verses", [])
    if not verses:
        return "No results found."
    # Cap output for readability
    lines = []
    for v in verses[:20]:
        ref = v.get("reference", f"{v['book']} {v['chapter']}:{v['verse']}")
        sim = f" (similarity: {v['similarity']})" if "similarity" in v else ""
        lines.append(f"{ref}{sim}\n  {v['text']}")
    return "\n\n".join(lines)


@mcp.tool()
def get_cross_references(book: str, chapter: int, verse: int) -> str:
    """Get cross-references for a specific verse, ranked by vote count.

    Args:
        book: Book name
        chapter: Chapter number
        verse: Verse number
    """
    data = _get(f"{WEBAPP_URL}/api/cross-references/{book}/{chapter}/{verse}")
    if not data:
        return f"No cross-references found for {book} {chapter}:{verse}"
    lines = []
    for xref in data:
        direction = xref.get("direction", "")
        lines.append(f"{xref['reference']} (votes: {xref['votes']}, {direction})")
    return "\n".join(lines)


# ============================================
# Chat / RAG Tools
# ============================================

@mcp.tool()
def chat_with_bible(message: str) -> str:
    """Ask a question about the Bible. Uses semantic search to find relevant verses
    and generates an AI response grounded in Scripture.

    Args:
        message: Your Bible question (e.g. "What does the Bible say about forgiveness?")
    """
    data = _post(f"{WEBAPP_URL}/api/chat", {"message": message})
    response = data.get("response", "")
    verses = data.get("verses", [])

    parts = [response]
    if verses:
        parts.append("\n--- Relevant Verses ---")
        for v in verses:
            ref = v.get("reference", f"{v['book']} {v['chapter']}:{v['verse']}")
            sim = f" (similarity: {v['similarity']})" if "similarity" in v else ""
            parts.append(f"{ref}{sim}: {v['text']}")
    return "\n".join(parts)


@mcp.tool()
def rag_query(query: str, include_references: bool = True) -> str:
    """Query the Bible RAG system with cross-reference support.
    Uses the dedicated RAG API with Ollama for deeper answers.

    Args:
        query: Bible question or topic
        include_references: Include cross-references in the context
    """
    data = _post(f"{RAG_URL}/query", {
        "query": query,
        "include_references": include_references,
    })
    parts = [
        f"Answer: {data.get('answer', '')}",
    ]
    ctx = data.get("context", "")
    if ctx:
        parts.append(f"\nContext:\n{ctx}")
    return "\n".join(parts)


# ============================================
# Analytics Tools
# ============================================

@mcp.tool()
def word_analysis(words: list[str], case_sensitive: bool = False) -> str:
    """Analyze how often words appear in the Old vs New Testament.

    Args:
        words: List of words to analyze (e.g. ["love", "faith", "hope"])
        case_sensitive: Whether the search should be case-sensitive
    """
    data = _post(f"{ANALYTICS_URL}/api/word-analysis", {
        "words": words,
        "case_sensitive": case_sensitive,
    })
    results = data.get("results", [])
    if not results:
        return "No results."
    lines = []
    for r in results:
        lines.append(
            f"'{r['word']}': {r['total_count']} total  "
            f"(OT: {r['old_testament_count']} [{r['old_testament_percentage']}%], "
            f"NT: {r['new_testament_count']} [{r['new_testament_percentage']}%])"
        )
        # Top 5 books
        top_books = sorted(r["books_distribution"].items(), key=lambda x: x[1], reverse=True)[:5]
        if top_books:
            book_strs = [f"{b}: {c}" for b, c in top_books]
            lines.append(f"  Top books: {', '.join(book_strs)}")
    return "\n".join(lines)


@mcp.tool()
def word_distribution(word: str) -> str:
    """Get detailed distribution of a word across all books of the Bible.

    Args:
        word: The word to analyze
    """
    data = _get(f"{ANALYTICS_URL}/api/word-distribution/{word}")
    total = data.get("total_occurrences", 0)
    book_dist = data.get("book_distribution", {})

    lines = [f"'{data.get('word', word)}': {total} total occurrences across {len(book_dist)} books"]

    # Sort by count descending
    sorted_books = sorted(book_dist.items(), key=lambda x: x[1], reverse=True)
    for book, count in sorted_books:
        lines.append(f"  {book}: {count}")
    return "\n".join(lines)


@mcp.tool()
def testament_stats() -> str:
    """Get overall statistics for the Old and New Testament (verse counts, book counts)."""
    data = _get(f"{ANALYTICS_URL}/api/testament-stats")
    ot = data["old_testament"]
    nt = data["new_testament"]
    return (
        f"Old Testament: {ot['total_books']} books, {ot['total_verses']} verses\n"
        f"New Testament: {nt['total_books']} books, {nt['total_verses']} verses\n"
        f"Total: {data['total_books']} books, {data['total_verses']} verses"
    )


@mcp.tool()
def book_stats() -> str:
    """Get verse and chapter counts for every book of the Bible."""
    data = _get(f"{ANALYTICS_URL}/api/book-stats")
    books = data.get("books", [])
    lines = []
    current_testament = None
    for b in books:
        if b["testament"] != current_testament:
            current_testament = b["testament"]
            lines.append(f"\n--- {current_testament} ---")
        lines.append(f"{b['book']}: {b['chapter_count']} chapters, {b['verse_count']} verses")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
