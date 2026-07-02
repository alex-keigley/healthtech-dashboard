# Healthtech Dashboard — pipeline container.
#
# Build context is the REPO ROOT (so db/migrations/ is reachable):
#   docker build -t healthtech-pipeline -f pipeline/Dockerfile .
#
# Expects the repo mounted at /app in production (docker-compose mounts
# ./db and ./data as volumes); this image also COPYs the pipeline source
# so it's runnable standalone (e.g. `docker run` without a compose mount).
FROM python:3.12-slim

WORKDIR /app

# supercronic runs the weekly schedule in docker-compose (service
# pipeline-cron overrides CMD with `supercronic /app/crontab`).
ARG TARGETARCH=amd64
ADD https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-linux-${TARGETARCH} /usr/local/bin/supercronic
RUN chmod +x /usr/local/bin/supercronic

# Install dependencies first for better layer caching.
COPY pipeline/requirements.txt ./pipeline/requirements.txt
RUN pip install --no-cache-dir -r ./pipeline/requirements.txt

# Pipeline source + migrations (single source of truth for the schema).
COPY pipeline/ ./pipeline/
COPY db/ ./db/

WORKDIR /app/pipeline

# DATABASE_PATH defaults to ../data/app.db relative to repo root when unset
# (db.py resolves this robustly regardless of cwd). SEC_USER_AGENT should
# always be set in production — see pipeline/README.md.
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "pipeline.run", "--days", "7"]
