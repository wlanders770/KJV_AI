#!/usr/bin/env python3
"""
Load Cross-References into MySQL and ChromaDB
Parses cross_references.txt from Bible database and loads into both storage systems.
"""

import mysql.connector
import chromadb
import re
from tqdm import tqdm
import os

# Database configuration
MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
MYSQL_PORT = int(os.getenv('MYSQL_PORT', '3307'))
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'password')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'bible')

CHROMA_HOST = os.getenv('CHROMA_HOST', 'localhost')
CHROMA_PORT = int(os.getenv('CHROMA_PORT', '8000'))

# Path to cross-references file
XREF_FILE = '/app/cross_references.txt'

# Book name mappings (abbreviation to full name)
BOOK_ABBREV = {
    'Gen': 'Genesis', 'Exod': 'Exodus', 'Lev': 'Leviticus', 'Num': 'Numbers', 'Deut': 'Deuteronomy',
    'Josh': 'Joshua', 'Judg': 'Judges', 'Ruth': 'Ruth', '1Sam': '1 Samuel', '2Sam': '2 Samuel',
    '1Kgs': '1 Kings', '2Kgs': '2 Kings', '1Chr': '1 Chronicles', '2Chr': '2 Chronicles',
    'Ezra': 'Ezra', 'Neh': 'Nehemiah', 'Esth': 'Esther', 'Job': 'Job', 'Ps': 'Psalm',
    'Prov': 'Proverbs', 'Eccl': 'Ecclesiastes', 'Song': 'Song of Solomon', 'Isa': 'Isaiah',
    'Jer': 'Jeremiah', 'Lam': 'Lamentations', 'Ezek': 'Ezekiel', 'Dan': 'Daniel',
    'Hos': 'Hosea', 'Joel': 'Joel', 'Amos': 'Amos', 'Obad': 'Obadiah', 'Jonah': 'Jonah',
    'Mic': 'Micah', 'Nah': 'Nahum', 'Hab': 'Habakkuk', 'Zeph': 'Zephaniah', 'Hag': 'Haggai',
    'Zech': 'Zechariah', 'Mal': 'Malachi',
    'Matt': 'Matthew', 'Mark': 'Mark', 'Luke': 'Luke', 'John': 'John', 'Acts': 'Acts',
    'Rom': 'Romans', '1Cor': '1 Corinthians', '2Cor': '2 Corinthians', 'Gal': 'Galatians',
    'Eph': 'Ephesians', 'Phil': 'Philippians', 'Col': 'Colossians', '1Thess': '1 Thessalonians',
    '2Thess': '2 Thessalonians', '1Tim': '1 Timothy', '2Tim': '2 Timothy', 'Titus': 'Titus',
    'Phlm': 'Philemon', 'Heb': 'Hebrews', 'Jas': 'James', '1Pet': '1 Peter', '2Pet': '2 Peter',
    '1John': '1 John', '2John': '2 John', '3John': '3 John', 'Jude': 'Jude', 'Rev': 'Revelation'
}

def parse_verse_reference(ref):
    """Parse a verse reference like 'Gen.1.1' or 'Ps.119.1-Ps.119.8'"""
    # Handle range references (e.g., Gen.1.1-Gen.1.3 or Prov.8.22-Prov.8.30)
    if '-' in ref:
        parts = ref.split('-')
        start_ref = parts[0]
        end_ref = parts[1] if len(parts) > 1 else start_ref
        
        # Parse start reference
        start_match = re.match(r'([A-Za-z0-9]+)\.(\d+)\.(\d+)', start_ref)
        if not start_match:
            return None
        
        book_abbrev = start_match.group(1)
        book = BOOK_ABBREV.get(book_abbrev, book_abbrev)
        chapter = int(start_match.group(2))
        verse_start = int(start_match.group(3))
        
        # Parse end reference (might be just verse number or full reference)
        if '.' in end_ref:
            end_match = re.match(r'([A-Za-z0-9]+)\.(\d+)\.(\d+)', end_ref)
            if end_match:
                verse_end = int(end_match.group(3))
            else:
                verse_end = verse_start
        else:
            verse_end = int(end_ref) if end_ref.isdigit() else verse_start
        
        return {
            'book': book,
            'chapter': chapter,
            'verse_start': verse_start,
            'verse_end': verse_end,
            'reference': f"{book} {chapter}:{verse_start}" + (f"-{verse_end}" if verse_end != verse_start else "")
        }
    else:
        # Single verse reference
        match = re.match(r'([A-Za-z0-9]+)\.(\d+)\.(\d+)', ref)
        if not match:
            return None
        
        book_abbrev = match.group(1)
        book = BOOK_ABBREV.get(book_abbrev, book_abbrev)
        chapter = int(match.group(2))
        verse = int(match.group(3))
        
        return {
            'book': book,
            'chapter': chapter,
            'verse_start': verse,
            'verse_end': verse,
            'reference': f"{book} {chapter}:{verse}"
        }

def get_verse_id(cursor, book, chapter, verse):
    """Get verse ID from MySQL database"""
    cursor.execute(
        "SELECT id FROM verses WHERE book = %s AND chapter = %s AND verse = %s",
        (book, chapter, verse)
    )
    result = cursor.fetchone()
    return result[0] if result else None

def get_verse_text(cursor, book, chapter, verse):
    """Get verse text from MySQL database"""
    cursor.execute(
        "SELECT text FROM verses WHERE book = %s AND chapter = %s AND verse = %s",
        (book, chapter, verse)
    )
    result = cursor.fetchone()
    return result[0] if result else ""

def main():
    print("=" * 60)
    print("Loading Cross-References into MySQL and ChromaDB")
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
    cursor = mysql_conn.cursor()
    print("   ✅ Connected to MySQL")
    
    # Connect to ChromaDB
    print(f"\n🔗 Connecting to ChromaDB at {CHROMA_HOST}:{CHROMA_PORT}...")
    chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    
    # Get or create cross-references collection
    try:
        xref_collection = chroma_client.get_collection("cross_references")
        print("   ℹ️  Collection 'cross_references' exists, deleting to reload...")
        chroma_client.delete_collection("cross_references")
    except:
        pass
    
    xref_collection = chroma_client.create_collection(
        name="cross_references",
        metadata={"hnsw:space": "cosine"}
    )
    print("   ✅ Connected to ChromaDB")
    
    # Clear existing cross-references in MySQL
    print("\n🗑️  Clearing existing cross-references in MySQL...")
    cursor.execute("DELETE FROM cross_references")
    mysql_conn.commit()
    print("   ✅ Cleared existing data")
    
    # Parse cross-references file
    print(f"\n📖 Reading cross-references from {XREF_FILE}...")
    xrefs_to_insert = []
    xref_embeddings = []
    skipped = 0
    
    with open(XREF_FILE, 'r') as f:
        lines = f.readlines()
    
    print(f"   ✅ Read {len(lines)} lines")
    
    # Open log file for failures
    log_file = open('/app/cross_references_failures.log', 'w')
    log_file.write("Failed Cross-References\n")
    log_file.write("=" * 80 + "\n\n")
    
    # Process cross-references
    print("\n🔄 Parsing cross-references...")
    for line_num, line in enumerate(tqdm(lines[1:], desc="Processing"), start=2):  # Skip header
        parts = line.strip().split('\t')
        if len(parts) < 3:
            skipped += 1
            log_file.write(f"Line {line_num}: Invalid format (< 3 fields): {line.strip()}\n")
            continue
        
        from_ref = parts[0]
        to_ref = parts[1]
        votes = int(parts[2]) if parts[2].lstrip('-').isdigit() else 0
        
        # Parse references
        source = parse_verse_reference(from_ref)
        target = parse_verse_reference(to_ref)
        
        if not source:
            skipped += 1
            log_file.write(f"Line {line_num}: Failed to parse source '{from_ref}'\n")
            continue
        
        if not target:
            skipped += 1
            log_file.write(f"Line {line_num}: Failed to parse target '{to_ref}'\n")
            continue
        
        # Get verse IDs
        source_id = get_verse_id(cursor, source['book'], source['chapter'], source['verse_start'])
        target_id = get_verse_id(cursor, target['book'], target['chapter'], target['verse_start'])
        
        if not source_id:
            skipped += 1
            log_file.write(f"Line {line_num}: Source verse not found: {source['book']} {source['chapter']}:{source['verse_start']} ({from_ref})\n")
            continue
        
        if not target_id:
            skipped += 1
            log_file.write(f"Line {line_num}: Target verse not found: {target['book']} {target['chapter']}:{target['verse_start']} ({to_ref})\n")
            continue
        
        # Prepare MySQL insert
        xrefs_to_insert.append((
            source_id,
            target_id,
            source['reference'],
            target['reference'],
            'cross_reference',
            votes
        ))
        
        # Prepare ChromaDB embedding (combine source and target text for semantic search)
        source_text = get_verse_text(cursor, source['book'], source['chapter'], source['verse_start'])
        target_text = get_verse_text(cursor, target['book'], target['chapter'], target['verse_start'])
        
        xref_embeddings.append({
            'id': f"xref_{source_id}_{target_id}",
            'document': f"{source['reference']}: {source_text} → {target['reference']}: {target_text}",
            'metadata': {
                'source_verse_id': source_id,
                'target_verse_id': target_id,
                'source_ref': source['reference'],
                'target_ref': target['reference'],
                'votes': votes
            }
        })
    
    print(f"   ✅ Parsed {len(xrefs_to_insert)} cross-references (skipped {skipped})")
    log_file.write(f"\n\nTotal skipped: {skipped}\n")
    log_file.write(f"Total loaded: {len(xrefs_to_insert)}\n")
    log_file.close()
    print(f"   📝 Failure log written to /app/cross_references_failures.log")
    
    # Insert into MySQL in batches to avoid timeout
    print("\n💾 Inserting cross-references into MySQL...")
    batch_size = 5000
    total_batches = (len(xrefs_to_insert) + batch_size - 1) // batch_size
    
    for i in range(0, len(xrefs_to_insert), batch_size):
        batch = xrefs_to_insert[i:i+batch_size]
        batch_num = i // batch_size + 1
        print(f"   Batch {batch_num}/{total_batches} ({len(batch)} records)...")
        cursor.executemany(
            """INSERT INTO cross_references 
               (source_verse_id, target_verse_id, source_ref, target_ref, relationship_type, votes)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            batch
        )
        mysql_conn.commit()
    print(f"   ✅ Inserted {len(xrefs_to_insert)} cross-references into MySQL")
    
    # Insert into ChromaDB in batches
    print("\n🚀 Adding cross-references to ChromaDB...")
    batch_size = 500
    for i in tqdm(range(0, len(xref_embeddings), batch_size), desc="Batches"):
        batch = xref_embeddings[i:i+batch_size]
        xref_collection.add(
            ids=[item['id'] for item in batch],
            documents=[item['document'] for item in batch],
            metadatas=[item['metadata'] for item in batch]
        )
    print(f"   ✅ Added {len(xref_embeddings)} cross-references to ChromaDB")
    
    # Verify counts
    print("\n✅ Verifying final counts...")
    cursor.execute("SELECT COUNT(*) FROM cross_references")
    mysql_count = cursor.fetchone()[0]
    chroma_count = xref_collection.count()
    
    print(f"   MySQL: {mysql_count} cross-references")
    print(f"   ChromaDB: {chroma_count} cross-references")
    
    # Close connections
    cursor.close()
    mysql_conn.close()
    
    print("\n" + "=" * 60)
    print("✅ SUCCESS! Cross-references loaded into both databases")
    print("=" * 60)

if __name__ == "__main__":
    main()
