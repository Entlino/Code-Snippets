from flask import Flask, g, request, jsonify, send_from_directory
import sqlite3
from ai_module import analyze_code_snippet
import json

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS snippets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL,
        tags TEXT,
        description TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        db.commit()


app = Flask(__name__)
DATABASE = 'snippets.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row  
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/add_snippet', methods=['POST'])
def add_snippet():
    data = request.get_json()
    code = data.get('code', '').strip()

    if not code:
        return jsonify({'error': 'Code snippet is required'}), 400

    print("Analysiere Code-Snippet mit AI...")
    analysis_result = analyze_code_snippet(code)
    tags = analysis_result.get('tags', 'code,snippet')
    description = analysis_result.get('description', 'Code-Snippet ohne weitere Beschreibung.')
    
    print(f"AI-Ergebnis - Tags: {tags}, Beschreibung: {description}")

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO snippets (code, tags, description) VALUES (?, ?, ?)",
        (code, tags, description)
    )
    db.commit()
    snippet_id = cursor.lastrowid

    return jsonify({
        'message': 'Snippet saved',
        'id': snippet_id,
        'tags': tags,
        'description': description
    }), 201


@app.route('/snippets', methods=['GET'])
def get_all_snippets():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, code, tags, description, created_at FROM snippets ORDER BY created_at DESC")
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

    return jsonify(snippets_list)

@app.route('/search', methods=['GET'])
def search_snippets():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT id, code, tags, description, created_at FROM snippets WHERE code LIKE ? OR tags LIKE ? OR description LIKE ? ORDER BY created_at DESC",
        (f'%{query}%', f'%{query}%', f'%{query}%')
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

@app.route('/snippet/<int:snippet_id>', methods=['GET'])
def get_snippet(snippet_id):
    """Einzelnes Snippet abrufen"""
    db = get_db()
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
        'created_at': snippet['created_at']
    })

@app.route('/snippet/<int:snippet_id>', methods=['DELETE'])
def delete_snippet(snippet_id):
    """Snippet löschen"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM snippets WHERE id = ?", (snippet_id,))
    
    if cursor.rowcount == 0:
        return jsonify({'error': 'Snippet not found'}), 404
    
    db.commit()
    return jsonify({'message': 'Snippet deleted'})

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM snippets")
        count = cursor.fetchone()[0]

        from ai_module import analyze_code_snippet
        test_result = analyze_code_snippet("print('test')")
        ai_available = bool(test_result.get('tags'))
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'snippets_count': count,
            'ai_available': ai_available
        })
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

    try:
        test_result = analyze_code_snippet("print('hello')")
        if test_result.get('tags'):
            print("✓ AI-Modul (CodeLlama) verfügbar")
        else:
            print("⚠ AI-Modul läuft im Fallback-Modus")
    except Exception as e:
        print(f"⚠ AI-Modul Fehler: {e}")
    
    app.run(debug=True, host='0.0.0.0', port=5000)