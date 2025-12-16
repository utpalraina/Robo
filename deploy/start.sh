#!/bin/bash
# Production Startup Script for Robo Trader

set -e

echo "=========================================="
echo "   Robo Trader - Production Startup"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running in Docker
if [ -f /.dockerenv ]; then
    echo -e "${GREEN}Running in Docker container${NC}"
    IN_DOCKER=true
else
    IN_DOCKER=false
fi

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
    echo -e "${GREEN}Loaded .env file${NC}"
else
    echo -e "${YELLOW}Warning: .env file not found${NC}"
fi

# Set defaults
export ENV=${ENV:-production}
export HOST=${HOST:-0.0.0.0}
export PORT=${PORT:-8000}
export WORKERS=${WORKERS:-4}
export LOG_LEVEL=${LOG_LEVEL:-info}

echo ""
echo "Configuration:"
echo "  Environment: $ENV"
echo "  Host: $HOST"
echo "  Port: $PORT"
echo "  Workers: $WORKERS"
echo ""

# Create necessary directories
mkdir -p logs data models

# Wait for dependencies (Redis, PostgreSQL)
if [ "$IN_DOCKER" = true ]; then
    echo "Waiting for Redis..."
    while ! nc -z ${REDIS_HOST:-redis} ${REDIS_PORT:-6379}; do
        sleep 1
    done
    echo -e "${GREEN}Redis is ready${NC}"

    if [ ! -z "$DATABASE_URL" ]; then
        echo "Waiting for PostgreSQL..."
        while ! nc -z ${DB_HOST:-postgres} ${DB_PORT:-5432}; do
            sleep 1
        done
        echo -e "${GREEN}PostgreSQL is ready${NC}"
    fi
fi

# Run database migrations (if needed)
# python -m alembic upgrade head

# Start the application
echo ""
echo "Starting Robo Trader..."
echo "=========================================="

exec gunicorn web.server:app \
    --bind ${HOST}:${PORT} \
    --workers ${WORKERS} \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout 120 \
    --graceful-timeout 30 \
    --keep-alive 5 \
    --max-requests 5000 \
    --max-requests-jitter 500 \
    --access-logfile - \
    --error-logfile - \
    --log-level ${LOG_LEVEL} \
    --capture-output
