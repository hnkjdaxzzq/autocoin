FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency specification first for layer caching
COPY pyproject.toml ./

# Install production dependencies only (no dev extras)
RUN uv pip install --system --no-cache .

# Copy application code
COPY autocoin/ autocoin/
COPY frontend/ frontend/
COPY main.py ./

# Default environment variables (override at runtime)
ENV AUTOCOIN_JWT_SECRET="change-me-in-production" \
    AUTOCOIN_DATABASE_URL="sqlite:////data/autocoin.db" \
    AUTOCOIN_CORS_ORIGINS='["*"]'

# Persist database outside the container image
VOLUME ["/data"]

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
