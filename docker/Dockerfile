FROM python:3.11-alpine

# Set working directory
WORKDIR /app

# Install system dependencies for building Python packages
RUN apk add --no-cache \
    gcc \
    musl-dev \
    linux-headers \
    g++ \
    make

# Copy requirements
COPY requirements.txt .

# Install Python dependencies with build tools
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt || \
    (pip install --no-cache-dir --only-binary :all: -r requirements.txt 2>/dev/null || true)

# Copy application code
COPY src/ src/

# Create data directory for SQLite database
RUN mkdir -p /app/data

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/api/health', timeout=5)" || exit 1

# Run application
CMD ["python", "-m", "src.main"]
