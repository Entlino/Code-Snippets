from flask import Flask, g
import sqlite3
from flask import request, jsonify
from flask import send_from_directory

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS snippets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                tags TEXT,
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


    tags = ''

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO snippets (code, tags) VALUES (?, ?)",
        (code, tags)
    )
    db.commit()
    snippet_id = cursor.lastrowid

    return jsonify({'message': 'Snippet saved', 'id': snippet_id}), 201

@app.route('/snippets', methods=['GET'])
def get_all_snippets():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, code, tags, created_at FROM snippets ORDER BY created_at DESC")
    snippets = cursor.fetchall()

    snippets_list = [
        {
            'id': row['id'],
            'code': row['code'],
            'tags': row['tags'],
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
    # Search in code or tags
    cursor.execute(
        "SELECT id, code, tags, created_at FROM snippets WHERE code LIKE ? OR tags LIKE ? ORDER BY created_at DESC",
        (f'%{query}%', f'%{query}%')
    )
    results = cursor.fetchall()

    snippets_list = [
        {
            'id': row['id'],
            'code': row['code'],
            'tags': row['tags'],
            'created_at': row['created_at']
        }
        for row in results
    ]

    return jsonify(snippets_list)

if __name__ == '__main__':
    init_db()

    app.run(debug=True)
