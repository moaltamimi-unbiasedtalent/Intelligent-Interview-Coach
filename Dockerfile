# Production image for Intelligent Interview Coach.
# Secrets are NEVER baked in — provide them at runtime via environment variables
# or a mounted secrets file (see docs/operations_deployment.md).

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# Install runtime dependencies first (better layer caching). The [db] extra adds
# Alembic + the PostgreSQL driver for production.
COPY pyproject.toml requirements.txt README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install ".[db]"

# Copy the application (tests, node_modules, secrets, data are excluded via
# .dockerignore).
COPY app.py alembic.ini ./
COPY migrations ./migrations
COPY components ./components
COPY scripts ./scripts
COPY .streamlit/config.toml ./.streamlit/config.toml

# Run as a non-root user.
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

# Streamlit UI on 8501 (default). The same image can also serve the FastAPI
# backend (Sprint 4 Phase 2) on 8000 via a command override — no separate image:
#   docker run -p 8000:8000 <image> \
#     uvicorn src.api.main:app --host 0.0.0.0 --port 8000
# FastAPI health: GET /api/health  (base path /api/v1).
EXPOSE 8501 8000

# Streamlit's built-in health endpoint (default CMD).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health').status==200 else 1)"

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
