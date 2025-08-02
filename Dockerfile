# Usa Python come base
FROM python:3.11-slim

# Imposta la directory di lavoro
WORKDIR /app

# Copia file requirements
COPY requirements.txt requirements.txt

# Installa dipendenze
RUN pip install --no-cache-dir -r requirements.txt

# Copia tutti i file nella directory di lavoro
COPY . .

# Esponi la porta
EXPOSE 8080

# Comando per avviare l'app Flask
CMD ["python", "main.py"]
