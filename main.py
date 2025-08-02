import os
import uuid
import xml.etree.ElementTree as ET
import requests
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("⚠️ ERRORE: Variabili d'ambiente SUPABASE_URL o SUPABASE_KEY mancanti o non valide.")
    print("L'app potrebbe non funzionare correttamente senza di esse.")
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
        r = requests.post(f"{SUPABASE_URL}/rest/v1/import_log?select=*", headers=HEADERS, json=log_data)
        print("Log response:", r.status_code, r.text)
        r.raise_for_status()
    except Exception as e:
        print("Errore nel logging:", str(e))
        if 'r' in locals():
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
        return existing[endpoint[:-1] + "_id"]
    print(f"Inserting new record into {endpoint}:", data)
    res = requests.post(f"{SUPABASE_URL}/rest/v1/{endpoint}?select=*", headers=HEADERS, json=data)
    print("Insert response:", res.status_code, res.text)
    res.raise_for_status()
    inserted = res.json()[0]
    return inserted[endpoint[:-1] + "_id"]

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Fatture Importer è attivo"}), 200

@app.route("/upload", methods=["POST"])
def upload():
    uploaded_file = request.files.get("file")
    if not uploaded_file:
        log_import("", "errore", "Nessun file ricevuto")
        return jsonify({"error": "Nessun file ricevuto"}), 400

    filename = uploaded_file.filename
    try:
        tree = ET.parse(uploaded_file)
        root = tree.getroot()
        ns = {}  # disabilita namespace perché il file XML non lo utilizza
        cedente = root.find(".//{http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.0}CedentePrestatore")
        if cedente is None:
            cedente = root.find(".//CedentePrestatore")  # fallback senza namespace
        if cedente is None:
            raise ValueError("CedentePrestatore non trovato nel file XML")

        denominazione = get_text_or_raise(
            cedente,
            "./DatiAnagrafici/"
            "Anagrafica/"
            "Denominazione",
            ns,
            "Denominazione Fornitore"
        )

        piva = get_text_or_raise(
            cedente,
            "./DatiAnagrafici/"
            "IdFiscaleIVA/"
            "IdCodice",
            ns,
            "Partita IVA Fornitore"
        )

        fornitore_id = insert_unique("fornitori", {"ragione_sociale": denominazione, "partita_iva": piva}, "partita_iva")
        log_import(filename, "ok", "Importazione completata", fornitore_id=fornitore_id)
        return jsonify({"message": "Importazione completata con successo"}), 200

    except Exception as e:
        print("Errore durante il parsing o inserimento:", str(e))
        log_import(filename, "errore", f"Errore durante l'importazione: {str(e)}")
        return jsonify({"error": f"Errore durante l'importazione: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
