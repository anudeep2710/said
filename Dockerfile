# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for PDF processing and database
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for temporary files
RUN mkdir -p /tmp/uploads

# Expose ports
EXPOSE 8080
EXPOSE 9090

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8080
ENV USE_MOCK_STORAGE=false
ENV USE_REAL_AI=true
ENV USE_SECRET_MANAGER=true
ENV ENVIRONMENT=production
ENV PROMETHEUS_PORT=9090

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/', timeout=10)" || exit 1

# Run the application (using original main.py for stability)
CMD exec uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1
