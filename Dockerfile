FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application files
COPY saas_core ./saas_core
COPY migrations ./migrations
COPY alembic.ini .
COPY examples ./examples

EXPOSE 8000

CMD ["uvicorn", "examples.minimal_fastapi.main:app", "--host", "0.0.0.0", "--port", "8000"]
