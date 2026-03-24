import csv
import chromadb

# 1. Get all data from your collection
# Assuming 'collection' is your KJV collection from previous steps
client = chromadb.HttpClient(host='127.0.0.1', port=8000)
collection_id = "kjv_bible"
collection = client.get_collection(name=collection_id)
data = collection.get(include=['embeddings', 'documents', 'metadatas'])

# 2. Save the Vectors (the 'points' in 3D space)
with open('vectors.tsv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f, delimiter='\t')
    for embedding in data['embeddings']:
        writer.writerow(embedding)

# 3. Save the Metadata (the labels for those points)
with open('metadata.tsv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f, delimiter='\t')
    writer.writerow(['Reference', 'Text']) # Headers
    for i in range(len(data['documents'])):
        ref = data['metadatas'][i]['reference']
        text = data['documents'][i]
        writer.writerow([ref, text])

print("Files 'vectors.tsv' and 'metadata.tsv' created!")