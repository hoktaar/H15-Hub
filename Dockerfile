FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
# Stub-Package erstellen damit hatchling die Dependencies auflösen kann
# (echte Sourcen werden danach kopiert – Docker-Layer-Cache bleibt erhalten)
RUN mkdir h15hub && touch h15hub/__init__.py \
    && pip install --no-cache-dir -e . \
    && rm -rf h15hub

COPY . .

# Placeholder damit Docker config.yaml korrekt als Datei (nicht Verzeichnis) mountet
RUN touch /app/config.yaml && mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "h15hub.main:app", "--host", "0.0.0.0", "--port", "8000"]
