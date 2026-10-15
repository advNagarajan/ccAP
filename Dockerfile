# Use official slim Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file first to leverage docker caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source code and worker codebase
COPY app/ ./app/
COPY workers/ ./workers/
COPY scripts/ ./scripts/
COPY sample_data/ ./sample_data/

# Set Python path to ensure module imports resolve correctly
ENV PYTHONPATH=/app

# Expose API port
EXPOSE 8080

# Default command runs the FastAPI server
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
