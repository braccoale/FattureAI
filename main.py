import os
import uuid
import xml.etree.ElementTree as ET
import requests
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def log_import(filename, status, message, fattura_id=None, fornitore_id=None, cliente_id=None):
    log_data = {
        "import_id": str(uuid.uuid4()),
        "filename": filename,
        "status": status,
        "error_message": message,
        "processed_at": datetime.utcnow().isoformat(),
        "fattura_id": fattura_id,
        "fornitore_id": fornitore_id,
        "cliente_id": cliente_id
    }
    print("Logging import:", log_data)
    try:
        r = requests.post(f"{SUPABASE_URL}/rest/v1/import_log", headers=HEADERS, json=log_data)
        print("Log response:", r.status_code, r.text)
        r.raise_for_status()
    except Exception as e:
        print("Errore nel logging:", str(e))
        if r is not None:
            print("Contenuto risposta Supabase:", r.text)

def get_text_or_none(element, path, ns):
    tag = element.find(path, ns)
    return tag.text.strip() if tag is not None and tag.text else None

def get_text_or_raise(element, path, ns, field_name):
    text = get_text_or_none(element, path, ns)
    if not text:
        raise ValueError(f"Campo '{field_name}' non trovato nel file XML")
    return text

def check_exists(endpoint, field, value):
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}?{field}=eq.{value}"
    print("Checking existence:", url)
    res = requests.get(url, headers=HEADERS)
    print("Check response:", res.status_code, res.text)
    if res.ok and res.json():
        return res.json()[0]
    return None

def insert_unique(endpoint, data, unique_field):
    existing = check_exists(endpoint, unique_field, data[unique_field])
    if existing:
        print(f"{endpoint} record already exists:", existing)
        return existing[endpoint[:-1] + "id"]
    print(f"Inserting new record into {endpoint}:", data)
    res = requests.post(f"{SUPABASE_URL}/rest/v1/{endpoint}?select=*",
