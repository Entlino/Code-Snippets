import requests
import json
import re
from typing import Dict

def analyze_code_snippet(code: str) -> Dict[str, str]:
    """Analysiert Code-Snippet mit CodeLama und gibt Tags + Beschreibung zurück"""
    
    # Fallback falls AI nicht verfügbar
    fallback = {
        'tags': 'code,snippet',
        'description': 'Code-Snippet'
    }
    
    try:
        # Ollama API aufrufen - Einfacherer Prompt der besser funktioniert
        prompt = f"""You are a code analysis AI. Your task is to analyze the provided code snippet and return a structured response with tags and a one sentence description.

Code:
{code[:800]}

Respond with exactly this format:
Tags: programming_language,framework,purpose,type
Description: Short sentence describing what this code does.
"""

        payload = {
            "model": "codellama:7b",
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Noch niedriger für konsistentere Ausgabe
                "max_tokens": 200,
                "top_p": 0.8
            }
        }
        
        response = requests.post(
            "http://localhost:11434/api/generate",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            ai_response = response.json().get('response', '').strip()
            print(f"AI Raw Response: {ai_response}")  # Debug
            parsed = parse_ai_response(ai_response)
            print(f"Parsed Result: {parsed}")  # Debug
            return parsed
            
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
    
    # Fallback: Wenn AI nicht das Format verwendet, trotzdem versuchen zu parsen
    lines = [line.strip() for line in ai_response.split('\n') if line.strip()]
    
    tags_found = False
    desc_found = False
    
    for line in lines:
        line_lower = line.lower()
        
        # Tags finden - flexibler
        if ('tags:' in line_lower or 'tag:' in line_lower) and not tags_found:
            tags_part = line.split(':', 1)[1].strip()
            # Bereinigen aber flexibler
            clean_tags = re.sub(r'[^a-zA-Z0-9,\-\+\#\._]', '', tags_part.lower())
            if clean_tags and ',' in clean_tags:  # Mindestens 2 Tags
                result['tags'] = clean_tags
                tags_found = True
        
        # Beschreibung finden - flexibler  
        elif (('description:' in line_lower or 'beschreibung:' in line_lower) and not desc_found):
            desc = line.split(':', 1)[1].strip()
            desc = re.sub(r'^["\']|["\']$', '', desc)  # Entfernt Anführungszeichen am Anfang/Ende
            if len(desc) > 10:
                result['description'] = desc
                desc_found = True
                
        # Fallback: Lange Zeilen als Beschreibung behandeln
        elif not desc_found and len(line) > 20 and not any(x in line_lower for x in ['tags', 'code', 'example']):
            desc = re.sub(r'^["\']|["\']$', '', line)
            if len(desc) > 10:
                result['description'] = desc
                desc_found = True
    
    # Wenn keine Tags gefunden, versuche aus dem Text zu extrahieren
    if not tags_found and ai_response:
        # Einfache Keyword-Erkennung als Fallback
        text = ai_response.lower()
        detected_tags = []
        
        # Sprachen
        languages = ['python', 'javascript', 'java', 'html', 'css', 'sql', 'bash', 'php', 'go', 'rust']
        for lang in languages:
            if lang in text:
                detected_tags.append(lang)
                break
        
        # Frameworks
        frameworks = ['flask', 'django', 'react', 'vue', 'express', 'bootstrap']
        for fw in frameworks:
            if fw in text:
                detected_tags.append(fw)
        
        # Zweck
        purposes = ['api', 'web', 'database', 'function', 'class', 'frontend', 'backend']
        for purpose in purposes:
            if purpose in text:
                detected_tags.append(purpose)
        
        if detected_tags:
            result['tags'] = ','.join(detected_tags[:10])  # Max 5 Tags
    
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