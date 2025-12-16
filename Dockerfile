# Robo Trader - Production Docker Image
# Multi-stage build for optimized production deployment

# ============ Build Stage ============
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ============ Production Stage ============
FROM python:3.11-slim as production

# Labels
LABEL maintainer="Robo Trader"
LABEL version="1.0"
LABEL description="ML-based Cryptocurrency Trading Bot"

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH" \
    ENV=production

# Create non-root user for security
RUN groupadd -r robotrader && useradd -r -g robotrader robotrader

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=robotrader:robotrader . .

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/models && \
    chown -R robotrader:robotrader /app

# Switch to non-root user
USER robotrader

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Default command
CMD ["gunicorn", "web.server:app", "-c", "deploy/gunicorn.conf.py"]
