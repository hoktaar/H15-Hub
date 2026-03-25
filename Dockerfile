FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml .
# Stub-Package erstellen damit hatchling die Dependencies auflösen kann
# (echte Sourcen werden danach kopiert – Docker-Layer-Cache bleibt erhalten)
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core git \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir h15hub && touch h15hub/__init__.py \
    && pip install --no-cache-dir -e ".[printers]" \
    && rm -rf h15hub

RUN pip install --no-cache-dir "git+https://github.com/luxardolabs/brother_ql.git"

COPY . .

RUN mkdir -p /app/config /app/data \
    && chmod +x /app/docker-entrypoint.sh

EXPOSE 8032

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "h15hub.main:app", "--host", "0.0.0.0", "--port", "8032"]
