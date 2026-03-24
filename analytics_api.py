#!/usr/bin/env python3
"""
KJV Bible Analytics API
Provides word analysis, distribution charts, and statistics
"""

import os
import re
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import mysql.connector
from collections import Counter, defaultdict
import json

app = FastAPI(title="KJV Bible Analytics API", version="1.0.0")

# CORS middleware for web UI access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration
MYSQL_HOST = os.getenv('MYSQL_HOST', 'mysql')
MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'password')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'bible')

# Old Testament books (39 books)
OLD_TESTAMENT_BOOKS = [
    'Genesis', 'Exodus', 'Leviticus', 'Numbers', 'Deuteronomy',
    'Joshua', 'Judges', 'Ruth', '1 Samuel', '2 Samuel',
    '1 Kings', '2 Kings', '1 Chronicles', '2 Chronicles',
    'Ezra', 'Nehemiah', 'Esther', 'Job', 'Psalms', 'Proverbs',
    'Ecclesiastes', 'Song of Solomon', 'Isaiah', 'Jeremiah', 'Lamentations',
    'Ezekiel', 'Daniel', 'Hosea', 'Joel', 'Amos', 'Obadiah',
    'Jonah', 'Micah', 'Nahum', 'Habakkuk', 'Zephaniah', 'Haggai',
    'Zechariah', 'Malachi'
]

def get_db_connection():
    """Create database connection"""
    return mysql.connector.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE
    )

def normalize_word(word: str) -> str:
    """Normalize word for searching (lowercase, remove punctuation)"""
    return re.sub(r'[^\w\s]', '', word.lower())

class WordSearchRequest(BaseModel):
    words: List[str]
    case_sensitive: bool = False

class WordStats(BaseModel):
    word: str
    total_count: int
    old_testament_count: int
    new_testament_count: int
    old_testament_percentage: float
    new_testament_percentage: float
    books_distribution: dict

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "KJV Bible Analytics API",
        "version": "1.0.0",
        "endpoints": {
            "dashboard": "/dashboard",
            "word_analysis": "/api/word-analysis",
            "word_distribution": "/api/word-distribution",
            "testament_stats": "/api/testament-stats",
            "book_stats": "/api/book-stats"
        }
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        conn = get_db_connection()
        conn.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.post("/api/word-analysis")
async def word_analysis(request: WordSearchRequest):
    """
    Analyze word frequency across Old and New Testament
    Returns counts, percentages, and book-level distribution
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        results = []
        
        for word in request.words:
            search_word = normalize_word(word)
            
            # Get all verses containing the word
            if request.case_sensitive:
                query = "SELECT book, chapter, verse, text FROM verses WHERE text LIKE %s"
            else:
                query = "SELECT book, chapter, verse, text FROM verses WHERE LOWER(text) LIKE %s"
            
            cursor.execute(query, (f'%{search_word}%',))
            verses = cursor.fetchall()
            
            # Count occurrences in each verse
            total_count = 0
            ot_count = 0
            nt_count = 0
            books_dist = defaultdict(int)
            
            for verse in verses:
                book = verse['book']
                text = verse['text'].lower() if not request.case_sensitive else verse['text']
                
                # Count word occurrences in this verse
                count = len(re.findall(r'\b' + re.escape(search_word) + r'\b', text))
                total_count += count
                books_dist[book] += count
                
                if book in OLD_TESTAMENT_BOOKS:
                    ot_count += count
                else:
                    nt_count += count
            
            # Calculate percentages
            ot_percentage = (ot_count / total_count * 100) if total_count > 0 else 0
            nt_percentage = (nt_count / total_count * 100) if total_count > 0 else 0
            
            results.append({
                "word": word,
                "total_count": total_count,
                "old_testament_count": ot_count,
                "new_testament_count": nt_count,
                "old_testament_percentage": round(ot_percentage, 2),
                "new_testament_percentage": round(nt_percentage, 2),
                "books_distribution": dict(books_dist)
            })
        
        cursor.close()
        conn.close()
        
        return {"results": results}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing words: {str(e)}")

@app.get("/api/word-distribution/{word}")
async def word_distribution(word: str, case_sensitive: bool = False):
    """
    Get detailed distribution of a word across all books
    Returns data suitable for plotting
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        search_word = normalize_word(word)
        
        # Get all verses
        cursor.execute("SELECT book, chapter, verse, text FROM verses ORDER BY id")
        all_verses = cursor.fetchall()
        
        # Track position and occurrences
        positions = []
        book_counts = defaultdict(int)
        testament_position = []
        
        for idx, verse in enumerate(all_verses):
            book = verse['book']
            text = verse['text'].lower() if not case_sensitive else verse['text']
            
            count = len(re.findall(r'\b' + re.escape(search_word) + r'\b', text))
            
            if count > 0:
                positions.append(idx)
                book_counts[book] += count
                testament = "Old Testament" if book in OLD_TESTAMENT_BOOKS else "New Testament"
                testament_position.append({
                    "position": idx,
                    "testament": testament,
                    "book": book,
                    "reference": f"{book} {verse['chapter']}:{verse['verse']}",
                    "count": count
                })
        
        cursor.close()
        conn.close()
        
        return {
            "word": word,
            "total_occurrences": len(positions),
            "positions": positions,
            "book_distribution": dict(book_counts),
            "testament_distribution": testament_position,
            "total_verses": len(all_verses)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing distribution: {str(e)}")

@app.get("/api/testament-stats")
async def testament_stats():
    """Get overall statistics for Old and New Testament"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Count verses in OT and NT
        cursor.execute("SELECT book, COUNT(*) as count FROM verses GROUP BY book")
        book_counts = cursor.fetchall()
        
        ot_verses = 0
        nt_verses = 0
        ot_books = []
        nt_books = []
        
        for item in book_counts:
            if item['book'] in OLD_TESTAMENT_BOOKS:
                ot_verses += item['count']
                ot_books.append({"book": item['book'], "verses": item['count']})
            else:
                nt_verses += item['count']
                nt_books.append({"book": item['book'], "verses": item['count']})
        
        cursor.close()
        conn.close()
        
        return {
            "old_testament": {
                "total_verses": ot_verses,
                "total_books": len(ot_books),
                "books": ot_books
            },
            "new_testament": {
                "total_verses": nt_verses,
                "total_books": len(nt_books),
                "books": nt_books
            },
            "total_verses": ot_verses + nt_verses,
            "total_books": len(ot_books) + len(nt_books)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching stats: {str(e)}")

@app.get("/api/book-stats")
async def book_stats():
    """Get verse counts and statistics for all books"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                book,
                COUNT(*) as verse_count,
                COUNT(DISTINCT chapter) as chapter_count
            FROM verses 
            GROUP BY book 
            ORDER BY MIN(id)
        """)
        
        books = cursor.fetchall()
        
        # Add testament information
        for book in books:
            book['testament'] = 'Old Testament' if book['book'] in OLD_TESTAMENT_BOOKS else 'New Testament'
        
        cursor.close()
        conn.close()
        
        return {"books": books}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching book stats: {str(e)}")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Interactive web dashboard for Bible analytics"""
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>KJV Bible Analytics Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        .header p {
            opacity: 0.9;
            font-size: 1.1em;
        }
        .controls {
            padding: 30px;
            background: #f8f9fa;
            border-bottom: 2px solid #e9ecef;
        }
        .input-group {
            display: flex;
            gap: 15px;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }
        input[type="text"] {
            flex: 1;
            min-width: 200px;
            padding: 12px 20px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
            transition: border 0.3s;
        }
        input[type="text"]:focus {
            outline: none;
            border-color: #667eea;
        }
        button {
            padding: 12px 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        button:active {
            transform: translateY(0);
        }
        .chart-container {
            padding: 30px;
        }
        .chart {
            margin-bottom: 40px;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            padding: 20px;
        }
        .loading {
            text-align: center;
            padding: 50px;
            color: #667eea;
            font-size: 1.2em;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 10px;
            text-align: center;
        }
        .stat-value {
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
        }
        .stat-label {
            opacity: 0.9;
            font-size: 1.1em;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 KJV Bible Analytics Dashboard</h1>
            <p>Explore word distributions and patterns across the Old and New Testament</p>
        </div>
        
        <div class="controls">
            <div class="input-group">
                <input type="text" id="wordInput" placeholder="Enter words separated by commas (e.g., love, faith, hope)" />
                <button onclick="analyzeWords()">Analyze Words</button>
                <button onclick="showTestamentStats()">Testament Overview</button>
            </div>
            <div style="color: #666; font-size: 0.9em; margin-top: 10px;">
                💡 Try: "love", "faith", "righteousness", "mercy", or compare multiple words
            </div>
        </div>
        
        <div class="chart-container">
            <div id="statsContainer"></div>
            <div id="charts"></div>
        </div>
    </div>

    <script>
        async function analyzeWords() {
            const input = document.getElementById('wordInput').value.trim();
            if (!input) {
                alert('Please enter at least one word');
                return;
            }
            
            const words = input.split(',').map(w => w.trim()).filter(w => w);
            
            document.getElementById('charts').innerHTML = '<div class="loading">🔍 Analyzing...</div>';
            document.getElementById('statsContainer').innerHTML = '';
            
            try {
                const response = await fetch('/api/word-analysis', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ words: words, case_sensitive: false })
                });
                
                const data = await response.json();
                displayResults(data.results);
                
                // Also fetch distribution for first word
                if (words.length > 0) {
                    const distResponse = await fetch(`/api/word-distribution/${encodeURIComponent(words[0])}`);
                    const distData = await distResponse.json();
                    displayDistribution(distData);
                }
                
            } catch (error) {
                document.getElementById('charts').innerHTML = `<div class="loading" style="color: red;">Error: ${error.message}</div>`;
            }
        }
        
        function displayResults(results) {
            // Create stats cards
            let statsHtml = '<div class="stats-grid">';
            results.forEach(r => {
                statsHtml += `
                    <div class="stat-card">
                        <div class="stat-label">${r.word.toUpperCase()}</div>
                        <div class="stat-value">${r.total_count}</div>
                        <div class="stat-label">Total Occurrences</div>
                    </div>
                `;
            });
            statsHtml += '</div>';
            document.getElementById('statsContainer').innerHTML = statsHtml;
            
            // Create testament comparison chart
            const words = results.map(r => r.word);
            const otCounts = results.map(r => r.old_testament_count);
            const ntCounts = results.map(r => r.new_testament_count);
            
            const testamentChart = {
                data: [
                    { x: words, y: otCounts, name: 'Old Testament', type: 'bar', marker: {color: '#667eea'} },
                    { x: words, y: ntCounts, name: 'New Testament', type: 'bar', marker: {color: '#764ba2'} }
                ],
                layout: {
                    title: 'Word Distribution: Old vs New Testament',
                    barmode: 'group',
                    xaxis: { title: 'Words' },
                    yaxis: { title: 'Occurrences' }
                }
            };
            
            // Create percentage chart
            const otPercentages = results.map(r => r.old_testament_percentage);
            const ntPercentages = results.map(r => r.new_testament_percentage);
            
            const percentageChart = {
                data: [
                    { x: words, y: otPercentages, name: 'Old Testament', type: 'bar', marker: {color: '#667eea'} },
                    { x: words, y: ntPercentages, name: 'New Testament', type: 'bar', marker: {color: '#764ba2'} }
                ],
                layout: {
                    title: 'Percentage Distribution by Testament',
                    barmode: 'stack',
                    xaxis: { title: 'Words' },
                    yaxis: { title: 'Percentage (%)' }
                }
            };
            
            let chartsHtml = '<div id="chart1" class="chart"></div><div id="chart2" class="chart"></div>';
            document.getElementById('charts').innerHTML = chartsHtml;
            
            Plotly.newPlot('chart1', testamentChart.data, testamentChart.layout, {responsive: true});
            Plotly.newPlot('chart2', percentageChart.data, percentageChart.layout, {responsive: true});
        }
        
        function displayDistribution(data) {
            // Create position scatter plot
            const otPositions = data.testament_distribution.filter(d => d.testament === 'Old Testament');
            const ntPositions = data.testament_distribution.filter(d => d.testament === 'New Testament');
            
            const scatterChart = {
                data: [
                    {
                        x: otPositions.map(d => d.position),
                        y: otPositions.map(d => d.count),
                        mode: 'markers',
                        name: 'Old Testament',
                        marker: { color: '#667eea', size: 8 },
                        text: otPositions.map(d => d.reference),
                        hovertemplate: '%{text}<br>Count: %{y}<extra></extra>'
                    },
                    {
                        x: ntPositions.map(d => d.position),
                        y: ntPositions.map(d => d.count),
                        mode: 'markers',
                        name: 'New Testament',
                        marker: { color: '#764ba2', size: 8 },
                        text: ntPositions.map(d => d.reference),
                        hovertemplate: '%{text}<br>Count: %{y}<extra></extra>'
                    }
                ],
                layout: {
                    title: `"${data.word}" - Distribution Across Bible (verse position)`,
                    xaxis: { title: 'Verse Position (0 = Genesis 1:1)' },
                    yaxis: { title: 'Occurrences in Verse' },
                    hovermode: 'closest'
                }
            };
            
            const chartDiv = document.createElement('div');
            chartDiv.className = 'chart';
            chartDiv.id = 'chart3';
            document.getElementById('charts').appendChild(chartDiv);
            
            Plotly.newPlot('chart3', scatterChart.data, scatterChart.layout, {responsive: true});
        }
        
        async function showTestamentStats() {
            document.getElementById('charts').innerHTML = '<div class="loading">📖 Loading statistics...</div>';
            document.getElementById('statsContainer').innerHTML = '';
            
            try {
                const response = await fetch('/api/testament-stats');
                const data = await response.json();
                
                // Create stats cards
                let statsHtml = `
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-label">Old Testament</div>
                            <div class="stat-value">${data.old_testament.total_verses.toLocaleString()}</div>
                            <div class="stat-label">${data.old_testament.total_books} Books</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">New Testament</div>
                            <div class="stat-value">${data.new_testament.total_verses.toLocaleString()}</div>
                            <div class="stat-label">${data.new_testament.total_books} Books</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">Total</div>
                            <div class="stat-value">${data.total_verses.toLocaleString()}</div>
                            <div class="stat-label">${data.total_books} Books</div>
                        </div>
                    </div>
                `;
                document.getElementById('statsContainer').innerHTML = statsHtml;
                
                // Create book distribution charts
                const otBooks = data.old_testament.books.map(b => b.book);
                const otVerses = data.old_testament.books.map(b => b.verses);
                const ntBooks = data.new_testament.books.map(b => b.book);
                const ntVerses = data.new_testament.books.map(b => b.verses);
                
                let chartsHtml = '<div id="chart1" class="chart"></div><div id="chart2" class="chart"></div>';
                document.getElementById('charts').innerHTML = chartsHtml;
                
                Plotly.newPlot('chart1', [{
                    x: otBooks,
                    y: otVerses,
                    type: 'bar',
                    marker: {color: '#667eea'}
                }], {
                    title: 'Old Testament - Verses per Book',
                    xaxis: { tickangle: -45 },
                    yaxis: { title: 'Number of Verses' }
                }, {responsive: true});
                
                Plotly.newPlot('chart2', [{
                    x: ntBooks,
                    y: ntVerses,
                    type: 'bar',
                    marker: {color: '#764ba2'}
                }], {
                    title: 'New Testament - Verses per Book',
                    xaxis: { tickangle: -45 },
                    yaxis: { title: 'Number of Verses' }
                }, {responsive: true});
                
            } catch (error) {
                document.getElementById('charts').innerHTML = `<div class="loading" style="color: red;">Error: ${error.message}</div>`;
            }
        }
        
        // Load initial stats on page load
        window.onload = () => showTestamentStats();
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
