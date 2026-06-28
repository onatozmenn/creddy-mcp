# Creddy - container image.
# Works on Hugging Face Spaces (Docker SDK), Render, Fly.io, Railway, etc.
# Requires a reachable Postgres (set CREDDY_DB_* env vars / secrets at runtime),
# e.g. a free serverless Postgres from Neon or Supabase (set CREDDY_DB_SSLMODE=require).
FROM python:3.11-slim

# Hugging Face Spaces run containers as a non-root user (UID 1000); match that so
# the app can write models/ at runtime.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PORT=7860

WORKDIR /app

COPY --chown=user pyproject.toml README.md ./
COPY --chown=user src ./src
COPY --chown=user sql ./sql
COPY --chown=user eval ./eval
COPY --chown=user docker-entrypoint.sh ./

RUN pip install --no-cache-dir --user -e .

EXPOSE 7860

CMD ["sh", "docker-entrypoint.sh"]
