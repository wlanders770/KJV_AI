#!/usr/bin/env python3
"""
Force reload of ALL verses into ChromaDB.
Deletes existing collection and reloads from KJV.txt
"""

import chromadb
import time
import os

CHROMA_HOST = os.getenv('CHROMA_HOST', 'chroma')  # Use 'chroma' for Docker network
CHROMA_PORT = int(os.getenv('CHROMA_PORT', 8000))
CHROMA_COLLECTION = "kjv_bible"
KJV_FILE = 'KJV.txt'

def main():
    print("\n" + "="*60)
    print("Force Reload All KJV Embeddings")
    print("="*60)
    
    # Connect to ChromaDB
    print(f"\n🔗 Connecting to ChromaDB at {CHROMA_HOST}:{CHROMA_PORT}...")
    try:
        client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        client.heartbeat()
        print("   ✅ Connected successfully")
    except Exception as e:
        print(f"   ❌ Failed to connect: {e}")
        print("   Make sure ChromaDB is running: docker-compose up -d chroma")
        return 1
    
    # Delete existing collection
    print(f"\n🗑️  Deleting existing collection '{CHROMA_COLLECTION}'...")
    try:
        client.delete_collection(name=CHROMA_COLLECTION)
        print("   ✅ Collection deleted")
    except Exception as e:
        print(f"   ℹ️  Collection may not exist: {e}")
    
    # Create new collection
    print(f"\n📦 Creating new collection '{CHROMA_COLLECTION}'...")
    try:
        collection = client.create_collection(
            name=CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"}
        )
        print("   ✅ Collection created")
    except Exception as e:
        print(f"   ❌ Failed to create collection: {e}")
        return 1
    
    # Load verses from KJV.txt
    print(f"\n📖 Loading verses from {KJV_FILE}...")
    verses = []
    verse_id = 0
    skipped = 0
    
    try:
        with open(KJV_FILE, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip empty lines, header lines, or comments
                if not line or line_num <= 2 or line.startswith('#'):
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
                    else:
                        skipped += 1
                except Exception as e:
                    skipped += 1
                    continue
        
        print(f"   ✅ Parsed {len(verses)} verses (skipped {skipped} lines)")
    
    except FileNotFoundError:
        print(f"   ❌ File not found: {KJV_FILE}")
        print("   Make sure you're running from the KJV_AI directory")
        return 1
    except Exception as e:
        print(f"   ❌ Error reading file: {e}")
        return 1
    
    if not verses:
        print("   ❌ No verses loaded!")
        return 1
    
    # Add to ChromaDB in batches
    print(f"\n🚀 Adding {len(verses)} verses to ChromaDB...")
    batch_size = 200
    total_batches = (len(verses) + batch_size - 1) // batch_size
    
    for batch_num, i in enumerate(range(0, len(verses), batch_size), 1):
        batch = verses[i:i+batch_size]
        texts = [v['text'] for v in batch]
        ids = [v['id'] for v in batch]
        metadatas = [
            {
                'ref': v['ref'], 
                'book': v['book'], 
                'chapter': str(v['chapter']), 
                'verse': str(v['verse'])
            } 
            for v in batch
        ]
        
        try:
            collection.add(
                documents=texts,
                ids=ids,
                metadatas=metadatas
            )
            
            # Progress indicator
            pct = (batch_num / total_batches) * 100
            print(f"   Progress: {batch_num}/{total_batches} batches ({pct:.1f}%) - {len(ids)} verses added", end='\r')
            
        except Exception as e:
            print(f"\n   ⚠️  Error adding batch {batch_num}: {e}")
            continue
    
    print()  # New line after progress
    
    # Verify count
    print(f"\n✅ Verifying final count...")
    final_count = collection.count()
    print(f"   ChromaDB now has {final_count} embeddings")
    
    if final_count == len(verses):
        print("\n" + "="*60)
        print("✅ SUCCESS! All verses loaded into ChromaDB")
        print("="*60)
        return 0
    else:
        print("\n" + "="*60)
        print(f"⚠️  WARNING: Expected {len(verses)} but got {final_count}")
        print("="*60)
        return 1

if __name__ == '__main__':
    exit(main())
