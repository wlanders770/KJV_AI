#!/usr/bin/env python3
"""
Load Cross-References into ChromaDB ONLY (MySQL already loaded)
Reads from MySQL cross_references table and creates semantic embeddings
"""

import mysql.connector
import chromadb
import os

# Database configuration
MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
MYSQL_PORT = int(os.getenv('MYSQL_PORT', '3307'))
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'password')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'bible')

CHROMA_HOST = os.getenv('CHROMA_HOST', 'localhost')
CHROMA_PORT = int(os.getenv('CHROMA_PORT', '8000'))

def main():
    print("=" * 60)
    print("Loading Cross-References into ChromaDB")
    print("=" * 60)
    
    # Connect to MySQL
    print(f"\n🔗 Connecting to MySQL at {MYSQL_HOST}:{MYSQL_PORT}...")
    mysql_conn = mysql.connector.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE
    )
    cursor = mysql_conn.cursor(dictionary=True)
    print("   ✅ Connected to MySQL")
    
    # Connect to ChromaDB
    print(f"\n🔗 Connecting to ChromaDB at {CHROMA_HOST}:{CHROMA_PORT}...")
    chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    
    # Delete and recreate collection
    try:
        chroma_client.delete_collection("cross_references")
        print("   ✅ Deleted existing collection")
    except:
        print("   ℹ️  No existing collection to delete")
    
    xref_collection = chroma_client.create_collection(
        name="cross_references",
        metadata={"hnsw:space": "cosine"}
    )
    print("   ✅ Created ChromaDB collection")
    
    # Read cross-references from MySQL
    print("\n📖 Reading cross-references from MySQL...")
    cursor.execute("""
        SELECT 
            cr.id, cr.source_verse_id, cr.target_verse_id,
            cr.source_ref, cr.target_ref, cr.votes,
            v1.text as source_text,
            v2.text as target_text
        FROM cross_references cr
        JOIN verses v1 ON cr.source_verse_id = v1.id
        JOIN verses v2 ON cr.target_verse_id = v2.id
        LIMIT 10000
    """)
    
    rows = cursor.fetchall()
    print(f"   ✅ Read {len(rows)} cross-references")
    
    # Prepare embeddings
    print("\n🔄 Preparing embeddings...")
    xref_embeddings = []
    for row in rows:
        xref_embeddings.append({
            'id': f"xref_{row['source_verse_id']}_{row['target_verse_id']}",
            'document': f"{row['source_ref']}: {row['source_text'][:200]} → {row['target_ref']}: {row['target_text'][:200]}",
            'metadata': {
                'source_verse_id': row['source_verse_id'],
                'target_verse_id': row['target_verse_id'],
                'source_ref': row['source_ref'],
                'target_ref': row['target_ref'],
                'votes': row['votes'] or 0
            }
        })
    print(f"   ✅ Prepared {len(xref_embeddings)} embeddings")
    
    # Insert into ChromaDB in small batches
    print("\n🚀 Adding to ChromaDB in small batches...")
    batch_size = 50
    total_batches = (len(xref_embeddings) + batch_size - 1) // batch_size
    
    for i in range(0, len(xref_embeddings), batch_size):
        batch = xref_embeddings[i:i+batch_size]
        batch_num = i // batch_size + 1
        
        try:
            xref_collection.add(
                ids=[item['id'] for item in batch],
                documents=[item['document'] for item in batch],
                metadatas=[item['metadata'] for item in batch]
            )
            print(f"   ✅ Batch {batch_num}/{total_batches} ({len(batch)} items)")
        except Exception as e:
            print(f"   ⚠️  Error in batch {batch_num}: {e}")
            continue
    
    # Verify count
    print("\n✅ Verifying...")
    chroma_count = xref_collection.count()
    print(f"   ChromaDB: {chroma_count} cross-references")
    
    cursor.close()
    mysql_conn.close()
    
    print("\n" + "=" * 60)
    print("✅ SUCCESS! Cross-references loaded into ChromaDB")
    print("=" * 60)

if __name__ == "__main__":
    main()
