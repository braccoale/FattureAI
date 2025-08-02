import os
import uuid
import xml.etree.ElementTree as ET
import requests
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
        "fattura_id": fattura_id,
        "fornitore_id": fornitore_id,
        "cliente_id": cliente_id
    }
    print("Logging import:", log_data)
    try:
        r = requests.post(f"{SUPABASE_URL}/import_log", headers=HEADERS, json=log_data)
        print("Log response:", r.status_code, r.text)
    except Exception as e:
        print("Errore nel logging:", str(e))

def check_exists(endpoint, field, value):
    url = f"{SUPABASE_URL}/{endpoint}?{field}=eq.{value}"
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
    res = requests.post(f"{SUPABASE_URL}/{endpoint}", headers=HEADERS, json=data)
    print("Insert response:", res.status_code, res.text)
    res.raise_for_status()
    return data[endpoint[:-1] + "id"]

@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "Nessun file XML allegato"}), 400

    file = request.files["file"]
    filename = file.filename
    try:
        print("Parsing file:", filename)
        tree = ET.parse(file)
        root = tree.getroot()

        # Auto-rileva namespace
        ns_uri = root.tag.split("}")[0].strip("{")
        ns = {"ns": ns_uri}

        cedente = next((el for el in root.iter() if el.tag.endswith("CedentePrestatore")), None)
        if cedente is None:
            raise ValueError("CedentePrestatore non trovato nel file XML")

        piva_fornitore = cedente.find(".//ns:IdFiscaleIVA/ns:IdCodice", ns).text
        denominazione_fornitore = cedente.find(".//ns:Denominazione", ns).text

        cessionario = next((el for el in root.iter() if el.tag.endswith("CessionarioCommittente")), None)
        if cessionario is None:
            raise ValueError("CessionarioCommittente non trovato nel file XML")

        piva_cliente = cessionario.find(".//ns:IdFiscaleIVA/ns:IdCodice", ns).text
        denominazione_cliente = cessionario.find(".//ns:Denominazione", ns).text

        numero_fattura = root.find(".//ns:DatiGeneraliDocumento/ns:Numero", ns).text
        data_fattura = root.find(".//ns:DatiGeneraliDocumento/ns:Data", ns).text
        importo_totale = float(root.find(".//ns:DatiGeneraliDocumento/ns:ImportoTotaleDocumento", ns).text)

        fornitore_id = insert_unique("fornitori", {
            "fornitoreid": str(uuid.uuid4()),
            "partita_iva": piva_fornitore,
            "denominazione": denominazione_fornitore
        }, "partita_iva")

        cliente_id = insert_unique("clienti", {
            "clientiid": str(uuid.uuid4()),
            "partita_iva": piva_cliente,
            "denominazione": denominazione_cliente
        }, "partita_iva")

        existing = check_exists("fatture", "numero", numero_fattura)
        if existing and existing.get("idfornitore") == fornitore_id:
            log_import(filename, "ignored", "Fattura già presente", existing["fatturaid"], fornitore_id, cliente_id)
            return jsonify({"message": "Fattura già presente. Ignorata."}), 200

        fattura_id = str(uuid.uuid4())
        fattura_payload = {
            "fatturaid": fattura_id,
            "codicecliente": cliente_id,
            "idfornitore": fornitore_id,
            "numero": numero_fattura,
            "data": data_fattura,
            "importototale": importo_totale,
            "filename": filename
        }
        print("Inserimento fattura:", fattura_payload)
        r = requests.post(f"{SUPABASE_URL}/fatture", headers=HEADERS, json=fattura_payload)
        print("Fattura response:", r.status_code, r.text)

        log_import(filename, "success", "Import riuscito", fattura_id, fornitore_id, cliente_id)
        return jsonify({"message": "Fattura importata con successo!"})

    except Exception as e:
        print("Errore nel parsing/upload:", str(e))
        log_import(filename, "error", str(e))
        return jsonify({"error": f"Errore durante l'importazione: {e}"}), 500

@app.route("/", methods=["GET"])
def root():
    return "Fattura Importer API attivo!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
