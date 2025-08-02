from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Fatture Importer è attivo"}), 200

@app.route("/", methods=["POST"])
def upload_file():
    uploaded_file = request.files.get("file")

    if not uploaded_file:
        return jsonify({"error": "Nessun file ricevuto"}), 400

    try:
        content = uploaded_file.read().decode("utf-8")
        print("Ricevuto file XML:", uploaded_file.filename)
        print(content)
        return jsonify({"message": "File ricevuto correttamente", "filename": uploaded_file.filename}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
