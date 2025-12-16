# Docker Guide

Complete guide for running Robo Trader with Docker and Docker Compose.

---

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+

### Install Docker

**macOS:**
```bash
brew install --cask docker
# Or download Docker Desktop from https://docker.com
```

**Ubuntu/Debian:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

**Verify Installation:**
```bash
docker --version
docker-compose --version
```

---

## Quick Start

```bash
# 1. Navigate to project
cd robo-trader

# 2. Create environment file
cp .env.production .env
nano .env  # Edit with your settings

# 3. Start all services
docker-compose up -d

# 4. Check status
docker-compose ps

# 5. View logs
docker-compose logs -f

# Access at: http://localhost
```

---

## Docker Commands Reference

### Using Management Script

The easiest way to manage Docker services:

```bash
# Make script executable (first time only)
chmod +x deploy/docker-start.sh

# Start services
./deploy/docker-start.sh start

# Stop services
./deploy/docker-start.sh stop

# Restart services
./deploy/docker-start.sh restart

# View logs
./deploy/docker-start.sh logs
./deploy/docker-start.sh logs app    # Specific service

# Check status
./deploy/docker-start.sh status

# Build/rebuild images
./deploy/docker-start.sh build

# Open shell in container
./deploy/docker-start.sh shell

# Start with monitoring (Prometheus + Grafana)
./deploy/docker-start.sh monitor

# Clean up (removes containers and volumes)
./deploy/docker-start.sh clean
```

### Using Docker Compose Directly

```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d app

# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Restart services
docker-compose restart

# View logs
docker-compose logs -f
docker-compose logs -f app
docker-compose logs -f --tail=100

# Check status
docker-compose ps

# Build images
docker-compose build
docker-compose build --no-cache

# Pull latest images
docker-compose pull

# Execute command in container
docker-compose exec app bash
docker-compose exec app python main.py --help

# Scale services
docker-compose up -d --scale worker=3
```

---

## Service Management

### Individual Services

```bash
# Start only the app
docker-compose up -d app

# Start app with dependencies (Redis, Postgres)
docker-compose up -d app --depends-on

# Restart single service
docker-compose restart app

# View service logs
docker-compose logs -f app

# Stop single service
docker-compose stop app
```

### Service Dependencies

```
nginx ──────► app ──────► redis
                 │
                 └──────► postgres

worker ─────► redis
         │
         └──► postgres

scheduler ──► redis
```

---

## Docker Compose Services

### Core Services

| Service | Image | Purpose |
|---------|-------|---------|
| `app` | Built from Dockerfile | Main FastAPI application |
| `nginx` | nginx:alpine | Reverse proxy |
| `redis` | redis:7-alpine | Cache & message broker |
| `postgres` | postgres:15-alpine | Database |
| `worker` | Built from Dockerfile | Celery workers |
| `scheduler` | Built from Dockerfile | Celery beat |

### Optional Services (Monitoring Profile)

| Service | Image | Purpose |
|---------|-------|---------|
| `prometheus` | prom/prometheus | Metrics collection |
| `grafana` | grafana/grafana | Dashboards |

Start with monitoring:
```bash
docker-compose --profile monitoring up -d
```

---

## Docker Compose Configuration

### Full docker-compose.yml Reference

```yaml
version: '3.8'

services:
  # Main application
  app:
    build: .
    ports:
      - "8000:8000"  # Exposed if not using Nginx
    environment:
      - ENV=production
      - REDIS_HOST=redis
      - DATABASE_URL=postgresql://user:pass@postgres/db
    volumes:
      - ./config:/app/config:ro
      - ./models:/app/models
      - ./data:/app/data
      - ./logs:/app/logs
    depends_on:
      - redis
      - postgres

  # Reverse proxy
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./deploy/nginx/robo-trader.conf:/etc/nginx/conf.d/default.conf
    depends_on:
      - app

  # Cache
  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data

  # Database
  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=robotrader
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=robotrader
    volumes:
      - postgres-data:/var/lib/postgresql/data

  # Background worker
  worker:
    build: .
    command: celery -A workers.celery_app worker --loglevel=info
    depends_on:
      - redis
      - postgres

volumes:
  redis-data:
  postgres-data:
```

---

## Volume Management

### Data Volumes

| Volume | Purpose | Persistent |
|--------|---------|------------|
| `redis-data` | Redis persistence | Yes |
| `postgres-data` | Database files | Yes |
| `./models` | Trained ML models | Yes (bind mount) |
| `./data` | Application data | Yes (bind mount) |
| `./logs` | Log files | Yes (bind mount) |

### Volume Commands

```bash
# List volumes
docker volume ls

# Inspect volume
docker volume inspect robo-trader_postgres-data

# Backup volume
docker run --rm -v robo-trader_postgres-data:/data -v $(pwd):/backup alpine tar cvf /backup/postgres-backup.tar /data

# Remove volumes
docker-compose down -v

# Remove specific volume
docker volume rm robo-trader_postgres-data
```

---

## Building Images

### Build Options

```bash
# Standard build
docker-compose build

# No cache (fresh build)
docker-compose build --no-cache

# Build specific service
docker-compose build app

# Build with build args
docker-compose build --build-arg ENV=production
```

### Dockerfile Stages

```dockerfile
# Build stage (installs dependencies)
FROM python:3.11-slim as builder
...

# Production stage (minimal image)
FROM python:3.11-slim as production
COPY --from=builder /opt/venv /opt/venv
...
```

---

## Environment Variables

### Passing Environment Variables

**Method 1: .env file**
```bash
# .env file is automatically loaded
docker-compose up -d
```

**Method 2: Command line**
```bash
DB_PASSWORD=secret docker-compose up -d
```

**Method 3: Environment file**
```bash
docker-compose --env-file .env.production up -d
```

---

## Networking

### Docker Network

```bash
# List networks
docker network ls

# Inspect network
docker network inspect robo-trader_robo-network

# Container IPs
docker-compose exec app hostname -i
```

### Service Discovery

Services can reach each other by name:
```python
# From app container
redis_host = "redis"      # Not localhost
db_host = "postgres"      # Not localhost
```

---

## Health Checks

### Built-in Health Checks

```yaml
# In docker-compose.yml
services:
  app:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

### Check Health Status

```bash
# View health status
docker-compose ps

# Detailed health info
docker inspect --format='{{json .State.Health}}' robo-trader-app
```

---

## Logging

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f app

# Last 100 lines
docker-compose logs --tail=100 app

# Since timestamp
docker-compose logs --since 2024-01-01T00:00:00 app
```

### Log Drivers

```yaml
# In docker-compose.yml
services:
  app:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

---

## Troubleshooting

### Common Issues

#### 1. Container Won't Start
```bash
# Check logs
docker-compose logs app

# Check if ports are in use
lsof -i :8000
```

#### 2. Database Connection Failed
```bash
# Check if postgres is running
docker-compose ps postgres

# Check postgres logs
docker-compose logs postgres

# Test connection
docker-compose exec postgres pg_isready
```

#### 3. Redis Connection Failed
```bash
# Check redis
docker-compose exec redis redis-cli ping
```

#### 4. Out of Disk Space
```bash
# Clean up unused resources
docker system prune -a

# Remove unused volumes
docker volume prune
```

#### 5. Permission Denied
```bash
# Fix volume permissions
sudo chown -R $USER:$USER ./data ./logs ./models
```

### Debug Commands

```bash
# Enter container shell
docker-compose exec app bash

# Run one-off command
docker-compose run --rm app python -c "print('test')"

# Check container resources
docker stats
```

---

## Production Deployment

### Pre-deployment Checklist

- [ ] Set secure passwords in `.env`
- [ ] Configure SSL certificates
- [ ] Set up backup strategy
- [ ] Configure monitoring
- [ ] Set resource limits
- [ ] Test all services

### Resource Limits

```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
```

---

## Next Steps

- [CLI Reference](./06-cli-reference.md) - Command line interface
- [API Reference](./07-api-reference.md) - REST API endpoints
