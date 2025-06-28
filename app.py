from flask import Flask, g, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import os
import logging
from datetime import datetime
from contextlib import contextmanager
from ai_module import analyze_code_snippet
import json

# Configuration
class Config:
    DATABASE = os.getenv('DATABASE_PATH', 'snippets.db')
    AI_TIMEOUT = int(os.getenv('AI_TIMEOUT', '30'))
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    PORT = int(os.getenv('FLASK_PORT', '5000'))

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Enable CORS for security
CORS(app, origins=['http://localhost:5000', 'http://127.0.0.1:5000'])

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database functions
@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def get_db():
    """Get database connection for Flask g object"""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(Config.DATABASE)
        db.row_factory = sqlite3.Row  
    return db

@app.teardown_appcontext
def close_connection(exception):
    """Close database connection on teardown"""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """Initialize database with required tables"""
    with app.app_context():
        try:
            with get_db_connection() as db:
                cursor = db.cursor()
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS snippets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    tags TEXT,
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # Add indexes for better search performance
                cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_snippets_tags ON snippets(tags)
                ''')
                cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_snippets_created_at ON snippets(created_at)
                ''')
                
                db.commit()
                logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise

# Routes
@app.route('/')
def index():
    """Serve main page"""
    return send_from_directory('.', 'index.html')

@app.route('/add_snippet', methods=['POST'])
def add_snippet():
    """Add a new code snippet with AI analysis"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
            
        code = data.get('code', '').strip()
        if not code:
            return jsonify({'error': 'Code snippet is required'}), 400
            
        if len(code) > 50000:  # Limit code size
            return jsonify({'error': 'Code snippet too large (max 50KB)'}), 400

        # AI analysis with timeout handling
        logger.info("Starting AI analysis of code snippet...")
        try:
            analysis_result = analyze_code_snippet(code)
            tags = analysis_result.get('tags', 'code,snippet')
            description = analysis_result.get('description', 'Code snippet without description.')
            logger.info(f"AI analysis complete - Tags: {tags[:50]}..., Description: {description[:50]}...")
        except Exception as e:
            logger.warning(f"AI analysis failed, using fallback: {e}")
            tags = 'code,snippet'
            description = 'Code snippet (AI analysis unavailable)'

        # Save to database
        with get_db_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """INSERT INTO snippets (code, tags, description, created_at, updated_at) 
                   VALUES (?, ?, ?, ?, ?)""",
                (code, tags, description, datetime.now(), datetime.now())
            )
            db.commit()
            snippet_id = cursor.lastrowid

        logger.info(f"Snippet {snippet_id} saved successfully")
        return jsonify({
            'message': 'Snippet saved successfully',
            'id': snippet_id,
            'tags': tags,
            'description': description
        }), 201

    except Exception as e:
        logger.error(f"Error adding snippet: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/snippets', methods=['GET'])
def get_all_snippets():
    """Get all snippets with pagination support"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)  # Max 100 per page
        offset = (page - 1) * per_page

        with get_db_connection() as db:
            cursor = db.cursor()
            
            # Get total count
            cursor.execute("SELECT COUNT(*) FROM snippets")
            total = cursor.fetchone()[0]
            
            # Get snippets with pagination
            cursor.execute(
                """SELECT id, code, tags, description, created_at 
                   FROM snippets 
                   ORDER BY created_at DESC 
                   LIMIT ? OFFSET ?""",
                (per_page, offset)
            )
            snippets = cursor.fetchall()

        snippets_list = [
            {
                'id': row['id'],
                'code': row['code'],
                'tags': row['tags'],
                'description': row['description'],
                'created_at': row['created_at']
            }
            for row in snippets
        ]

        return jsonify({
            'snippets': snippets_list,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        })

    except Exception as e:
        logger.error(f"Error fetching snippets: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/search', methods=['GET'])
def search_snippets():
    """Search snippets with improved query handling"""
    try:
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify([])
            
        if len(query) > 100:  # Limit query length
            return jsonify({'error': 'Search query too long'}), 400

        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        offset = (page - 1) * per_page

        with get_db_connection() as db:
            cursor = db.cursor()
            
            # Search with relevance scoring
            search_query = f'%{query}%'
            cursor.execute(
                """SELECT id, code, tags, description, created_at,
                   (CASE 
                    WHEN tags LIKE ? THEN 3
                    WHEN description LIKE ? THEN 2  
                    WHEN code LIKE ? THEN 1
                    ELSE 0 
                   END) as relevance
                   FROM snippets 
                   WHERE code LIKE ? OR tags LIKE ? OR description LIKE ?
                   ORDER BY relevance DESC, created_at DESC
                   LIMIT ? OFFSET ?""",
                (search_query, search_query, search_query, search_query, search_query, search_query, per_page, offset)
            )
            results = cursor.fetchall()

        snippets_list = [
            {
                'id': row['id'],
                'code': row['code'],
                'tags': row['tags'],
                'description': row['description'],
                'created_at': row['created_at']
            }
            for row in results
        ]

        return jsonify(snippets_list)

    except Exception as e:
        logger.error(f"Error searching snippets: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/snippet/<int:snippet_id>', methods=['GET'])
def get_snippet(snippet_id):
    """Get a single snippet by ID"""
    try:
        with get_db_connection() as db:
            cursor = db.cursor()
            cursor.execute("SELECT * FROM snippets WHERE id = ?", (snippet_id,))
            snippet = cursor.fetchone()
            
        if not snippet:
            return jsonify({'error': 'Snippet not found'}), 404
        
        return jsonify({
            'id': snippet['id'],
            'code': snippet['code'],
            'tags': snippet['tags'],
            'description': snippet['description'],
            'created_at': snippet['created_at'],
            'updated_at': snippet.get('updated_at', snippet['created_at'])
        })

    except Exception as e:
        logger.error(f"Error fetching snippet {snippet_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/snippet/<int:snippet_id>', methods=['PUT'])
def update_snippet(snippet_id):
    """Update an existing snippet"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
            
        code = data.get('code', '').strip()
        if not code:
            return jsonify({'error': 'Code snippet is required'}), 400

        with get_db_connection() as db:
            cursor = db.cursor()
            
            # Check if snippet exists
            cursor.execute("SELECT id FROM snippets WHERE id = ?", (snippet_id,))
            if not cursor.fetchone():
                return jsonify({'error': 'Snippet not found'}), 404
            
            # Re-analyze with AI if code changed
            analysis_result = analyze_code_snippet(code)
            tags = analysis_result.get('tags', 'code,snippet')
            description = analysis_result.get('description', 'Updated code snippet')
            
            cursor.execute(
                """UPDATE snippets 
                   SET code = ?, tags = ?, description = ?, updated_at = ?
                   WHERE id = ?""",
                (code, tags, description, datetime.now(), snippet_id)
            )
            db.commit()

        return jsonify({
            'message': 'Snippet updated successfully',
            'id': snippet_id,
            'tags': tags,
            'description': description
        })

    except Exception as e:
        logger.error(f"Error updating snippet {snippet_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/snippet/<int:snippet_id>', methods=['DELETE'])
def delete_snippet(snippet_id):
    """Delete a snippet"""
    try:
        with get_db_connection() as db:
            cursor = db.cursor()
            cursor.execute("DELETE FROM snippets WHERE id = ?", (snippet_id,))
            
            if cursor.rowcount == 0:
                return jsonify({'error': 'Snippet not found'}), 404
            
            db.commit()
            
        logger.info(f"Snippet {snippet_id} deleted successfully")
        return jsonify({'message': 'Snippet deleted successfully'})

    except Exception as e:
        logger.error(f"Error deleting snippet {snippet_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Comprehensive health check endpoint"""
    try:
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'disconnected',
            'snippets_count': 0,
            'ai_available': False
        }
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

if __name__ == '__main__':
    init_db()
    print("Starte Code Snippet Manager...")
    print("AI-Modul wird geladen...")
    
    # Test AI connection on startup
    try:
        test_result = analyze_code_snippet("print('hello')")
        if test_result.get('tags'):
            print("✓ AI-Modul (DeepSeek-Coder) verfügbar")
        else:
            print("⚠ AI-Modul läuft im Fallback-Modus")
    except Exception as e:
        print(f"⚠ AI-Modul Fehler: {e}")
    
    app.run(debug=True, host='0.0.0.0', port=5000)