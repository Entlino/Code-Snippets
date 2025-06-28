import requests
import json
import re
from typing import Dict

def analyze_code_snippet(code: str) -> Dict[str, str]:
    """Analysiert Code-Snippet mit DeepSeek-Coder und gibt Tags + Beschreibung zurück"""
    
    # Fallback falls AI nicht verfügbar
    fallback = {
        'tags': 'code,snippet',
        'description': 'Code-Snippet'
    }
    
    try:
        # Ollama API aufrufen
        prompt = f"""Du bist ein Code-Experte. Analysiere diesen Code und gib mir eine präzise Antwort:

```
{code[:1000]}
```

Antworte exakt in diesem Format:
TAGS: tag1,tag2,tag3,tag4,tag5,tag6
BESCHREIBUNG: Ein präziser Satz was dieser Code macht.

Fokus auf: Programmiersprache, Framework, Zweck, Komplexität, Design Pattern."""

        payload = {
            "model": "deepseek-coder:1.3b",
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "max_tokens": 200
            }
        }
        
        response = requests.post(
            "http://localhost:11434/api/generate",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            ai_response = response.json().get('response', '').strip()
            return parse_ai_response(ai_response)
            
    except Exception as e:
        print(f"AI-Analyse fehlgeschlagen: {e}")
    
    return fallback

def parse_ai_response(ai_response: str) -> Dict[str, str]:
    """Extrahiert Tags und Beschreibung aus AI-Antwort"""
    result = {
        'tags': 'code,snippet',
        'description': 'Code-Snippet'
    }
    
    if not ai_response:
        return result
    
    lines = ai_response.split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Tags finden
        if line.upper().startswith('TAGS:') or line.upper().startswith('TAG:'):
            tags_part = line.split(':', 1)[1].strip()
            # Nur erlaubte Zeichen für Tags
            clean_tags = re.sub(r'[^a-zA-Z0-9,\-\+\#\.]', '', tags_part.lower())
            if clean_tags and len(clean_tags) > 3:
                result['tags'] = clean_tags
        
        # Beschreibung finden
        elif (line.upper().startswith('BESCHREIBUNG:') or 
              line.upper().startswith('DESCRIPTION:') or
              (len(line) > 15 and not line.upper().startswith('TAGS'))):
            
            if ':' in line:
                desc = line.split(':', 1)[1].strip()
            else:
                desc = line.strip()
            
            # Anführungszeichen entfernen und validieren
            desc = re.sub(r'^["\']|["\']$', '', desc)
            if len(desc) > 10:
                result['description'] = desc
                break
    
    return result

# Test (kann in Produktion entfernt werden)
if __name__ == "__main__":
    test_code = """
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/api/users', methods=['GET'])
def get_users():
    return jsonify({'users': ['alice', 'bob']})
"""
    
    result = analyze_code_snippet(test_code)
    print("Tags:", result['tags'])
    print("Description:", result['description'])