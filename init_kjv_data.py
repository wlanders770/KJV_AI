#!/usr/bin/env python3
"""
Initialize KJV Bible data in ChromaDB and MySQL.
Runs automatically when docker-compose starts if data doesn't exist.
"""

import os
import sys
import time
import json
import chromadb
import mysql.connector
from pathlib import Path

# Configuration from environment or defaults
CHROMA_HOST = os.getenv('CHROMA_HOST', 'localhost')
CHROMA_PORT = int(os.getenv('CHROMA_PORT', 8000))
MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))  # Internal port in container
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'password')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'bible')

CHROMA_COLLECTION = "kjv_bible"
DATA_DIR = Path('/app/data') if os.path.exists('/app/data') else Path('./kjv_data')
KJV_FILE = DATA_DIR / 'KJV.txt'
CROSS_REF_FILE = DATA_DIR / 'cross_references.json'

# Try to find KJV.txt in parent directory too
if not KJV_FILE.exists():
    alt_path = Path('/app/KJV.txt')
    if alt_path.exists():
        KJV_FILE = alt_path
    else:
        alt_path = Path('./KJV.txt')
        if alt_path.exists():
            KJV_FILE = alt_path

def wait_for_service(host, port, name, timeout=60):
    """Wait for a service to be ready."""
    import socket
    start = time.time()
    while time.time() - start < timeout:
        try:
            socket.create_connection((host, port), timeout=2)
            print(f"   ✅ {name} is ready")
            return True
        except (socket.timeout, ConnectionRefusedError):
            print(f"   ⏳ Waiting for {name}...", end='\r')
            time.sleep(2)
    print(f"   ❌ {name} did not start in time")
    return False

def init_mysql():
    """Initialize MySQL with KJV verses and cross-references."""
    print("\n📊 Initializing MySQL Database...")
    
    # Wait for MySQL
    if not wait_for_service(MYSQL_HOST, MYSQL_PORT, "MySQL"):
        return False
    
    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
        )
        cursor = conn.cursor()
        
        # Check if verses table exists and has data
        cursor.execute("SHOW TABLES LIKE 'verses'")
        table_exists = cursor.fetchone()
        
        if table_exists:
            cursor.execute("SELECT COUNT(*) FROM verses")
            count = cursor.fetchone()[0]
            if count > 0:
                print(f"   ℹ️  Verses table already populated with {count} verses")
                cursor.close()
                conn.close()
                return True
            # Table exists but is empty - we'll load it below
            print(f"   Found empty verses table, loading data...")
        else:
            print(f"   Verses table does not exist, creating...")
        
        # Create verses table
        print("   Creating verses table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verses (
                id INT AUTO_INCREMENT PRIMARY KEY,
                book VARCHAR(50) NOT NULL,
                chapter INT NOT NULL,
                verse INT NOT NULL,
                text LONGTEXT NOT NULL,
                book_id INT,
                UNIQUE KEY unique_verse (book, chapter, verse)
            )
        """)
        
        # Load verses from KJV.txt
        if KJV_FILE.exists():
            print(f"   Loading verses from {KJV_FILE.name}...")
            verses = []
            
            with open(KJV_FILE, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line_num <= 2:
                        continue
                    if line.startswith('#'):
                        continue
                    try:
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            ref = parts[0]  # "Genesis 1:1"
                            text = '\t'.join(parts[1:])  # The verse text
                            # Parse reference
                            book, chapter_verse = ref.rsplit(' ', 1)
                            chapter, verse = chapter_verse.split(':')
                            verses.append((book, int(chapter), int(verse), text, None))
                    except Exception as e:
                        continue
            
            if verses:
                print(f"   Found {len(verses)} verses, loading into MySQL...")
                # Load all verses
                try:
                    cursor.executemany(
                        "INSERT IGNORE INTO verses (book, chapter, verse, text, book_id) VALUES (%s, %s, %s, %s, %s)",
                        verses
                    )
                    conn.commit()
                    loaded_count = cursor.rowcount
                    print(f"   ✅ Loaded {loaded_count} verses into MySQL")
                except Exception as e:
                    print(f"   ❌ Error loading verses: {e}")
                    conn.rollback()
                    loaded_count = 0
            else:
                print(f"   ⚠️  No verses found in {KJV_FILE.name}")
        
        # Create cross-references table
        print("   Creating cross-references table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cross_references (
                id INT AUTO_INCREMENT PRIMARY KEY,
                source_verse_id INT,
                target_verse_id INT,
                source_ref VARCHAR(50),
                target_ref VARCHAR(50),
                relationship_type VARCHAR(50),
                votes INT DEFAULT 0,
                FOREIGN KEY (source_verse_id) REFERENCES verses(id),
                FOREIGN KEY (target_verse_id) REFERENCES verses(id)
            )
        """)
        
        # Load cross-references if available
        if CROSS_REF_FILE.exists():
            print(f"   Loading cross-references from {CROSS_REF_FILE.name}...")
            with open(CROSS_REF_FILE, 'r') as f:
                cross_refs = json.load(f)
                # This would need proper mapping - placeholder for now
                print(f"   ℹ️  Cross-references file found but requires manual mapping")
        
        cursor.close()
        conn.close()
        print("   ✅ MySQL initialization complete")
        return True
        
    except Exception as e:
        print(f"   ❌ MySQL initialization failed: {e}")
        return False

def init_chromadb():
    """Initialize ChromaDB with embeddings."""
    print("\n🔍 Initializing ChromaDB...")
    
    # Wait for ChromaDB
    if not wait_for_service(CHROMA_HOST, CHROMA_PORT, "ChromaDB"):
        return False
    
    try:
        client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        
        # Check if collection exists and has data
        collection = None
        try:
            collection = client.get_collection(name=CHROMA_COLLECTION)
            count = collection.count()
            if count > 0:
                print(f"   ℹ️  Collection '{CHROMA_COLLECTION}' already has {count} embeddings")
                return True
            else:
                print(f"   Found empty collection, deleting to reload...")
                client.delete_collection(name=CHROMA_COLLECTION)
        except Exception as e:
            print(f"   Collection does not exist, creating new...")
        
        # Create collection
        print(f"   Creating collection '{CHROMA_COLLECTION}'...")
        try:
            collection = client.create_collection(
                name=CHROMA_COLLECTION,
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            print(f"   Error creating collection: {e}")
            return False
        
        # Load verses from KJV.txt
        if KJV_FILE.exists():
            print(f"   Loading embeddings from {KJV_FILE.name}...")
            verses = []
            verse_id = 0
            
            with open(KJV_FILE, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line_num <= 2:
                        continue
                    if line.startswith('#'):
                        continue
                    try:
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            ref = parts[0]  # "Genesis 1:1"
                            text = '\t'.join(parts[1:])  # The verse text
                            # Parse reference
                            book, chapter_verse = ref.rsplit(' ', 1)
                            chapter, verse = chapter_verse.split(':')
                            verses.append({
                                'id': str(verse_id),
                                'text': text,
                                'ref': ref,
                                'book': book,
                                'chapter': chapter,
                                'verse': verse
                            })
                            verse_id += 1
                    except Exception as e:
                        continue
            
            if verses:
                # Add to collection in batches
                batch_size = 200
                for i in range(0, len(verses), batch_size):
                    batch = verses[i:i+batch_size]
                    texts = [v['text'] for v in batch]
                    ids = [v['id'] for v in batch]
                    metadatas = [{'ref': v['ref'], 'book': v['book'], 'chapter': str(v['chapter']), 'verse': str(v['verse'])} for v in batch]
                    
                    collection.add(
                        documents=texts,
                        ids=ids,
                        metadatas=metadatas
                    )
                    print(f"   ✅ Added {min(batch_size, len(batch))} embeddings to ChromaDB", end='\r')
                
                print(f"\n   ✅ Loaded {len(verses)} embeddings into ChromaDB")
        
        print("   ✅ ChromaDB initialization complete")
        return True
        
    except Exception as e:
        print(f"   ❌ ChromaDB initialization failed: {e}")
        return False

def main():
    """Main initialization routine."""
    print("\n" + "="*60)
    print("KJV Bible Data Initialization")
    print("="*60)
    
    # Create data directory
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Initialize services
    mysql_ok = init_mysql()
    chromadb_ok = init_chromadb()
    
    print("\n" + "="*60)
    if mysql_ok and chromadb_ok:
        print("✅ All databases initialized successfully!")
        print("="*60)
        return 0
    else:
        print("❌ Some initialization steps failed")
        print("="*60)
        return 1

if __name__ == '__main__':
    sys.exit(main())
