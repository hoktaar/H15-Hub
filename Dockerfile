FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
# Stub-Package erstellen damit hatchling die Dependencies auflösen kann
# (echte Sourcen werden danach kopiert – Docker-Layer-Cache bleibt erhalten)
RUN mkdir h15hub && touch h15hub/__init__.py \
    && pip install --no-cache-dir -e . \
    && rm -rf h15hub

COPY . .

RUN mkdir -p /app/config /app/data \
    && chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "h15hub.main:app", "--host", "0.0.0.0", "--port", "8000"]
