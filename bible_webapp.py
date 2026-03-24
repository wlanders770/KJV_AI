#!/usr/bin/env python3
"""
KJV Bible Web Application
- Chat with Bible using RAG
- Read through Bible by book/chapter/verse
"""

from flask import Flask, render_template, request, jsonify, Response, g
from functools import wraps
import chromadb
import mysql.connector
import os
import json
import requests
import hashlib
import secrets
import time
from typing import List, Dict, Optional
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))

# Configuration
CHROMA_HOST = os.getenv('CHROMA_HOST', 'chroma')
CHROMA_PORT = int(os.getenv('CHROMA_PORT', 8000))
MYSQL_HOST = os.getenv('MYSQL_HOST', 'mysql')
MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'password')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'bible')
OLLAMA_URL = os.getenv('OLLAMA_URL', 'https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/runsync')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'mistral:7b')

# Bible book names (in order)
BIBLE_BOOKS = [
    # Old Testament
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
    "Joshua", "Judges", "Ruth", "1 Samuel", "2 Samuel",
    "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles",
    "Ezra", "Nehemiah", "Esther", "Job", "Psalms", "Proverbs",
    "Ecclesiastes", "Song of Solomon", "Isaiah", "Jeremiah", "Lamentations",
    "Ezekiel", "Daniel", "Hosea", "Joel", "Amos", "Obadiah",
    "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah",
    "Haggai", "Zechariah", "Malachi",
    # New Testament
    "Matthew", "Mark", "Luke", "John", "Acts",
    "Romans", "1 Corinthians", "2 Corinthians", "Galatians", "Ephesians",
    "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians",
    "1 Timothy", "2 Timothy", "Titus", "Philemon",
    "Hebrews", "James", "1 Peter", "2 Peter",
    "1 John", "2 John", "3 John", "Jude", "Revelation"
]

# Initialize connections
chroma_client = None
mysql_conn = None

# ============================================
# Auth helpers
# ============================================

def hash_password(password: str) -> str:
    """Hash a password with a random salt."""
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{h}"

def verify_password(password: str, stored: str) -> bool:
    """Verify a password against its stored hash."""
    salt, h = stored.split(':')
    return hashlib.sha256((salt + password).encode()).hexdigest() == h

def generate_token() -> str:
    """Generate a 64-char hex token."""
    return secrets.token_hex(32)

def init_auth_tables():
    """Create users and sessions tables if they don't exist."""
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                display_name VARCHAR(200),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                token VARCHAR(64) UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                INDEX idx_token (token),
                INDEX idx_expires (expires_at)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reading_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                book VARCHAR(50) NOT NULL,
                chapter INT NOT NULL,
                verse INT NOT NULL DEFAULT 0,
                visited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                INDEX idx_user_time (user_id, visited_at)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reading_position (
                user_id INT PRIMARY KEY,
                book VARCHAR(50) NOT NULL,
                chapter INT NOT NULL,
                verse INT NOT NULL DEFAULT 0,
                forward_stack JSON,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("Auth tables initialized successfully")
    except Exception as e:
        print(f"Error initializing auth tables: {e}")

def get_current_user():
    """Extract and validate the auth token from the request. Returns user_id or None."""
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    token = auth[7:]
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT s.user_id, u.username, u.display_name
            FROM sessions s JOIN users u ON s.user_id = u.id
            WHERE s.token = %s AND s.expires_at > NOW()
        """, (token,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row
    except Exception:
        return None

def require_auth(f):
    """Decorator requiring a valid Bearer token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        g.user = user
        return f(*args, **kwargs)
    return decorated

# Initialize auth tables on first request
_auth_tables_initialized = False

@app.before_request
def ensure_auth_tables():
    global _auth_tables_initialized
    if not _auth_tables_initialized:
        init_auth_tables()
        _auth_tables_initialized = True

def get_chroma_client():
    """Get ChromaDB client."""
    global chroma_client
    if chroma_client is None:
        chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    return chroma_client

def get_mysql_connection():
    """Get MySQL connection."""
    return mysql.connector.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE
    )

def semantic_search(query: str, n_results: int = 5) -> List[Dict]:
    """Perform semantic search using ChromaDB."""
    try:
        client = get_chroma_client()
        collection = client.get_collection(name='kjv_bible')
        
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        verses = []
        for doc, meta, dist in zip(
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0]
        ):
            verses.append({
                'reference': meta['ref'],
                'text': doc,
                'similarity': round(1 - dist, 3),
                'book': meta['book'],
                'chapter': meta['chapter'],
                'verse': meta['verse']
            })
        
        return verses
    except Exception as e:
        print(f"Error in semantic search: {e}")
        return []

def get_verses_by_reference(book: str, chapter: int, start_verse: int = None, end_verse: int = None) -> List[Dict]:
    """Get verses from MySQL by book and chapter."""
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor(dictionary=True)
        
        if start_verse and end_verse:
            query = """
                SELECT book, chapter, verse, text 
                FROM verses 
                WHERE book = %s AND chapter = %s AND verse BETWEEN %s AND %s
                ORDER BY verse
            """
            cursor.execute(query, (book, chapter, start_verse, end_verse))
        elif start_verse:
            query = """
                SELECT book, chapter, verse, text 
                FROM verses 
                WHERE book = %s AND chapter = %s AND verse = %s
            """
            cursor.execute(query, (book, chapter, start_verse))
        else:
            query = """
                SELECT book, chapter, verse, text 
                FROM verses 
                WHERE book = %s AND chapter = %s
                ORDER BY verse
            """
            cursor.execute(query, (book, chapter))
        
        verses = cursor.fetchall()
        cursor.close()
        conn.close()
        return verses
    except Exception as e:
        print(f"Error fetching verses: {e}")
        return []

def get_book_structure() -> Dict:
    """Get all books with their chapter counts."""
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT book, MAX(chapter) as chapters 
            FROM verses 
            GROUP BY book
        """
        cursor.execute(query)
        
        structure = {}
        for book, chapters in cursor.fetchall():
            structure[book] = chapters
        
        cursor.close()
        conn.close()
        return structure
    except Exception as e:
        print(f"Error fetching book structure: {e}")
        return {}

def get_cross_references(book: str, chapter: int, verse: int) -> List[Dict]:
    """Get cross-references for a specific verse"""
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get the verse ID first
        cursor.execute(
            "SELECT id FROM verses WHERE book = %s AND chapter = %s AND verse = %s",
            (book, chapter, verse)
        )
        verse_row = cursor.fetchone()
        if not verse_row:
            cursor.close()
            conn.close()
            return []
        
        verse_id = verse_row['id']
        
        # Get cross-references (both directions)
        cursor.execute("""
            SELECT target_ref as reference, votes, 'outgoing' as direction
            FROM cross_references
            WHERE source_verse_id = %s
            UNION ALL
            SELECT source_ref as reference, votes, 'incoming' as direction
            FROM cross_references
            WHERE target_verse_id = %s
            ORDER BY votes DESC
            LIMIT 50
        """, (verse_id, verse_id))
        
        xrefs = cursor.fetchall()
        cursor.close()
        conn.close()
        return xrefs
    except Exception as e:
        print(f"Error fetching cross-references: {e}")
        return []

def generate_response(query: str, context_verses: List[Dict]) -> str:
    """Generate AI response using Ollama."""
    try:
        # Build context from verses
        context = "\n\n".join([
            f"{v['reference']}: {v['text']}"
            for v in context_verses
        ])
        
        prompt = f"""You are a knowledgeable Bible scholar. Answer the question based on these relevant Bible verses.

Context from Scripture:
{context}

Question: {query}

Provide a clear, thoughtful answer referencing the verses above. Include verse references in your response."""

        # For local Ollama (if available)
        try:
            response = requests.post(
                'http://localhost:11434/api/generate',
                json={
                    'model': 'mistral',
                    'prompt': prompt,
                    'stream': False
                },
                timeout=30
            )
            if response.status_code == 200:
                return response.json().get('response', 'Unable to generate response')
        except:
            pass
        
        # Fallback: Just return context with references
        answer_parts = [
            "Here are the most relevant Bible verses for your question:\n"
        ]
        for v in context_verses:
            answer_parts.append(f"\n**{v['reference']}**\n{v['text']}")
        
        return "\n".join(answer_parts)
        
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Unable to generate response at this time."

# Routes
@app.route('/')
def index():
    """Main page with chat and reader."""
    return render_template('index.html', books=BIBLE_BOOKS)

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages."""
    data = request.json
    query = data.get('message', '')
    
    if not query:
        return jsonify({'error': 'No message provided'}), 400
    
    # Search for relevant verses
    relevant_verses = semantic_search(query, n_results=5)
    
    # Generate response
    response = generate_response(query, relevant_verses)
    
    return jsonify({
        'response': response,
        'verses': relevant_verses
    })

@app.route('/api/books', methods=['GET'])
def get_books():
    """Get list of all books with chapter counts."""
    structure = get_book_structure()
    return jsonify({
        'books': [
            {'name': book, 'chapters': structure.get(book, 0)}
            for book in BIBLE_BOOKS
        ]
    })

@app.route('/api/chapter/<book>/<int:chapter>', methods=['GET'])
def get_chapter(book, chapter):
    """Get all verses for a specific chapter."""
    verses = get_verses_by_reference(book, chapter)
    return jsonify({'verses': verses})

@app.route('/api/cross-references/<book>/<int:chapter>/<int:verse>')
def api_cross_references(book, chapter, verse):
    """Get cross-references for a specific verse"""
    xrefs = get_cross_references(book, chapter, verse)
    return jsonify(xrefs)

@app.route('/api/verse-by-reference/<path:reference>')
def get_verse_by_reference(reference):
    """Get verse text by reference string like 'John 3:16'"""
    try:
        # Parse reference like "Genesis 1:1" or "1 John 3:16"
        import re
        match = re.match(r'^(.+?)\s+(\d+):(\d+)(?:-(\d+))?$', reference)
        if not match:
            return jsonify({'error': 'Invalid reference format'}), 400
        
        book = match.group(1)
        chapter = int(match.group(2))
        verse_start = int(match.group(3))
        verse_end = int(match.group(4)) if match.group(4) else verse_start
        
        verses = get_verses_by_reference(book, chapter, verse_start, verse_end)
        if verses:
            return jsonify({'verses': verses, 'reference': reference})
        return jsonify({'error': 'Verse not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/verse/<book>/<int:chapter>/<int:verse>', methods=['GET'])
def get_verse(book, chapter, verse):
    """Get a specific verse."""
    verses = get_verses_by_reference(book, chapter, verse, verse)
    if verses:
        return jsonify({'verse': verses[0]})
    return jsonify({'error': 'Verse not found'}), 404

@app.route('/api/search', methods=['POST'])
def search_bible():
    """Search Bible text."""
    data = request.json
    query = data.get('query', '')
    search_type = data.get('type', 'semantic')  # semantic or keyword
    
    if not query:
        return jsonify({'error': 'No query provided'}), 400
    
    if search_type == 'semantic':
        verses = semantic_search(query, n_results=10)
    else:
        # Keyword search in MySQL - get all results from both testaments
        try:
            conn = get_mysql_connection()
            cursor = conn.cursor(dictionary=True)
            
            query_pattern = f"%{query}%"
            
            # New Testament books for filtering
            nt_books = ('Matthew','Mark','Luke','John','Acts','Romans',
                       '1 Corinthians','2 Corinthians','Galatians','Ephesians',
                       'Philippians','Colossians','1 Thessalonians','2 Thessalonians',
                       '1 Timothy','2 Timothy','Titus','Philemon','Hebrews','James',
                       '1 Peter','2 Peter','1 John','2 John','3 John','Jude','Revelation')
            
            # Get all OT results
            sql_ot = """
                SELECT book, chapter, verse, text,
                       CONCAT(book, ' ', chapter, ':', verse) as reference
                FROM verses 
                WHERE text LIKE %s AND book NOT IN ({})
                ORDER BY id
            """.format(','.join(['%s'] * len(nt_books)))
            cursor.execute(sql_ot, (query_pattern,) + nt_books)
            ot_verses = cursor.fetchall()
            
            # Get all NT results
            sql_nt = """
                SELECT book, chapter, verse, text,
                       CONCAT(book, ' ', chapter, ':', verse) as reference
                FROM verses 
                WHERE text LIKE %s AND book IN ({})
                ORDER BY id
            """.format(','.join(['%s'] * len(nt_books)))
            cursor.execute(sql_nt, (query_pattern,) + nt_books)
            nt_verses = cursor.fetchall()
            
            # Combine results: interleave OT and NT for better distribution
            verses = []
            for i in range(max(len(ot_verses), len(nt_verses))):
                if i < len(ot_verses):
                    verses.append(ot_verses[i])
                if i < len(nt_verses):
                    verses.append(nt_verses[i])
            
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Error in keyword search: {e}")
            verses = []
    
    return jsonify({'verses': verses})

# ============================================
# Auth Routes
# ============================================

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user."""
    data = request.json or {}
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')
    display_name = data.get('displayName', '').strip() or username

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    if len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    try:
        conn = get_mysql_connection()
        cursor = conn.cursor(dictionary=True)

        # Check if username exists
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Username already taken'}), 409

        # Create user
        pw_hash = hash_password(password)
        cursor.execute(
            "INSERT INTO users (username, password_hash, display_name) VALUES (%s, %s, %s)",
            (username, pw_hash, display_name)
        )
        user_id = cursor.lastrowid

        # Create session token (30-day expiry)
        token = generate_token()
        expires = datetime.utcnow() + timedelta(days=30)
        cursor.execute(
            "INSERT INTO sessions (user_id, token, expires_at) VALUES (%s, %s, %s)",
            (user_id, token, expires)
        )

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'token': token,
            'user': {
                'id': user_id,
                'username': username,
                'displayName': display_name
            }
        }), 201
    except Exception as e:
        print(f"Registration error: {e}")
        return jsonify({'error': 'Registration failed'}), 500


@app.route('/api/auth/login', methods=['POST'])
def login():
    """Authenticate a user and return a session token."""
    data = request.json or {}
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    try:
        conn = get_mysql_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id, username, password_hash, display_name FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

        if not user or not verify_password(password, user['password_hash']):
            cursor.close()
            conn.close()
            return jsonify({'error': 'Invalid username or password'}), 401

        # Create new session token (30-day expiry)
        token = generate_token()
        expires = datetime.utcnow() + timedelta(days=30)
        cursor.execute(
            "INSERT INTO sessions (user_id, token, expires_at) VALUES (%s, %s, %s)",
            (user['id'], token, expires)
        )

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'token': token,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'displayName': user['display_name'] or user['username']
            }
        })
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'error': 'Login failed'}), 500


@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def logout():
    """Invalidate the current session token."""
    token = request.headers.get('Authorization', '')[7:]
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE token = %s", (token,))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception:
        pass
    return jsonify({'ok': True})


@app.route('/api/auth/me', methods=['GET'])
@require_auth
def get_me():
    """Return the currently authenticated user."""
    return jsonify({
        'user': {
            'id': g.user['user_id'],
            'username': g.user['username'],
            'displayName': g.user['display_name'] or g.user['username']
        }
    })


# ============================================
# Reading History & Position Routes
# ============================================

@app.route('/api/reading/position', methods=['GET'])
@require_auth
def get_reading_position():
    """Get the user's last reading position and forward stack."""
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT book, chapter, verse, forward_stack FROM reading_position WHERE user_id = %s",
            (g.user['user_id'],)
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row:
            fwd = json.loads(row['forward_stack']) if row['forward_stack'] else []
            return jsonify({
                'position': {
                    'book': row['book'],
                    'chapter': row['chapter'],
                    'verse': row['verse']
                },
                'forwardStack': fwd
            })
        return jsonify({'position': None, 'forwardStack': []})
    except Exception as e:
        print(f"Error getting reading position: {e}")
        return jsonify({'error': 'Failed to get position'}), 500


@app.route('/api/reading/position', methods=['PUT'])
@require_auth
def save_reading_position():
    """Save user's current reading position and forward stack."""
    data = request.json or {}
    book = data.get('book', '')
    chapter = data.get('chapter', 0)
    verse = data.get('verse', 0)
    forward_stack = json.dumps(data.get('forwardStack', []))

    if not book or not chapter:
        return jsonify({'error': 'book and chapter required'}), 400

    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO reading_position (user_id, book, chapter, verse, forward_stack)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                book = VALUES(book),
                chapter = VALUES(chapter),
                verse = VALUES(verse),
                forward_stack = VALUES(forward_stack)
        """, (g.user['user_id'], book, chapter, verse, forward_stack))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        print(f"Error saving reading position: {e}")
        return jsonify({'error': 'Failed to save position'}), 500


@app.route('/api/reading/history', methods=['GET'])
@require_auth
def get_reading_history():
    """Get the user's reading history (back stack), most recent first."""
    limit = request.args.get('limit', 100, type=int)
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT book, chapter, verse, visited_at
            FROM reading_history
            WHERE user_id = %s
            ORDER BY visited_at DESC
            LIMIT %s
        """, (g.user['user_id'], limit))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        history = [{
            'book': r['book'],
            'chapter': r['chapter'],
            'verse': r['verse'],
            'visitedAt': r['visited_at'].isoformat() if r['visited_at'] else None
        } for r in rows]

        return jsonify({'history': history})
    except Exception as e:
        print(f"Error getting reading history: {e}")
        return jsonify({'error': 'Failed to get history'}), 500


@app.route('/api/reading/history', methods=['POST'])
@require_auth
def add_reading_history():
    """Push a new entry onto the reading history."""
    data = request.json or {}
    book = data.get('book', '')
    chapter = data.get('chapter', 0)
    verse = data.get('verse', 0)

    if not book or not chapter:
        return jsonify({'error': 'book and chapter required'}), 400

    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO reading_history (user_id, book, chapter, verse) VALUES (%s, %s, %s, %s)",
            (g.user['user_id'], book, chapter, verse)
        )

        # Keep only last 100 entries per user
        cursor.execute("""
            DELETE FROM reading_history
            WHERE user_id = %s AND id NOT IN (
                SELECT id FROM (
                    SELECT id FROM reading_history
                    WHERE user_id = %s
                    ORDER BY visited_at DESC
                    LIMIT 100
                ) tmp
            )
        """, (g.user['user_id'], g.user['user_id']))

        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'ok': True}), 201
    except Exception as e:
        print(f"Error adding reading history: {e}")
        return jsonify({'error': 'Failed to add history'}), 500


@app.route('/api/reading/history', methods=['DELETE'])
@require_auth
def clear_reading_history():
    """Clear all reading history for the current user."""
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM reading_history WHERE user_id = %s", (g.user['user_id'],))
        cursor.execute("DELETE FROM reading_position WHERE user_id = %s", (g.user['user_id'],))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        print(f"Error clearing history: {e}")
        return jsonify({'error': 'Failed to clear history'}), 500


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
