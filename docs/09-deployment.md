# Production Deployment Guide

Complete guide for deploying Robo Trader to production.

---

## Deployment Options

| Option | Complexity | Scalability | Best For |
|--------|------------|-------------|----------|
| **Docker Compose** | Low | Medium | Single server |
| **Kubernetes** | High | High | Multi-server clusters |
| **Cloud PaaS** | Low | High | Managed deployment |

---

## Pre-Deployment Checklist

### Security
- [ ] Change all default passwords
- [ ] Set secure `SECRET_KEY`
- [ ] Configure SSL/TLS certificates
- [ ] Set up firewall rules
- [ ] Enable rate limiting
- [ ] Review API authentication

### Configuration
- [ ] Set `ENV=production`
- [ ] Set `DEBUG=false`
- [ ] Configure production database (PostgreSQL)
- [ ] Set up Redis with password
- [ ] Configure exchange API keys
- [ ] Set appropriate log levels

### Infrastructure
- [ ] Provision server (4+ GB RAM recommended)
- [ ] Install Docker and Docker Compose
- [ ] Configure domain and DNS
- [ ] Set up SSL certificate
- [ ] Configure backup strategy
- [ ] Set up monitoring

---

## Docker Compose Deployment

### 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

### 2. Clone and Configure

```bash
# Clone repository
git clone <repository-url> /opt/robo-trader
cd /opt/robo-trader

# Create environment file
cp .env.production .env

# Edit with production values
nano .env
```

### 3. Production Environment Variables

```bash
# .env
ENV=production
DEBUG=false
SECRET_KEY=your-very-long-random-secret-key-here

# Database
DB_PASSWORD=strong-database-password-here
DATABASE_URL=postgresql://robotrader:strong-database-password-here@postgres:5432/robotrader

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Exchange (use real keys, testnet=false)
BINANCE_API_KEY=your-real-api-key
BINANCE_API_SECRET=your-real-api-secret
BINANCE_TESTNET=false

# Security
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
CORS_ORIGINS=https://your-domain.com
```

### 4. SSL Certificate Setup

**Option A: Let's Encrypt (Free)**

```bash
# Install Certbot
sudo apt install certbot

# Get certificate
sudo certbot certonly --standalone -d your-domain.com

# Copy certificates
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem deploy/nginx/ssl/
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem deploy/nginx/ssl/
```

**Option B: Self-Signed (Development)**

```bash
# Generate self-signed certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout deploy/nginx/ssl/robo-trader.key \
  -out deploy/nginx/ssl/robo-trader.crt
```

### 5. Update Nginx for HTTPS

Edit `deploy/nginx/robo-trader.conf`:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    # ... rest of configuration
}
```

### 6. Deploy

```bash
# Build and start
docker-compose up -d --build

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

---

## System Service Setup

### Create systemd Service

```bash
sudo nano /etc/systemd/system/robo-trader.service
```

```ini
[Unit]
Description=Robo Trader
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/robo-trader
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl enable robo-trader
sudo systemctl start robo-trader

# Check status
sudo systemctl status robo-trader
```

---

## Monitoring Setup

### Enable Prometheus & Grafana

```bash
# Start with monitoring profile
docker-compose --profile monitoring up -d
```

Access:
- Prometheus: http://your-domain.com:9090
- Grafana: http://your-domain.com:3000

### Configure Alerts

In Grafana, set up alerts for:
- High CPU/Memory usage
- Application errors
- Trading anomalies
- Database connection issues

---

## Backup Strategy

### Database Backup

```bash
# Create backup script
cat > /opt/robo-trader/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups/robo-trader"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup PostgreSQL
docker-compose exec -T postgres pg_dump -U robotrader robotrader > $BACKUP_DIR/db_$DATE.sql

# Backup models
tar -czf $BACKUP_DIR/models_$DATE.tar.gz models/

# Backup config
tar -czf $BACKUP_DIR/config_$DATE.tar.gz config/ .env

# Keep only last 7 days
find $BACKUP_DIR -type f -mtime +7 -delete

echo "Backup completed: $DATE"
EOF

chmod +x /opt/robo-trader/backup.sh
```

### Schedule Daily Backups

```bash
# Add to crontab
crontab -e

# Add line (runs daily at 2 AM)
0 2 * * * /opt/robo-trader/backup.sh >> /var/log/robo-trader-backup.log 2>&1
```

---

## Scaling

### Horizontal Scaling

```bash
# Scale app workers
docker-compose up -d --scale app=3

# Scale Celery workers
docker-compose up -d --scale worker=5
```

### Load Balancing

Update Nginx upstream:

```nginx
upstream robo_trader_app {
    least_conn;
    server app_1:8000;
    server app_2:8000;
    server app_3:8000;
}
```

---

## Security Hardening

### 1. Firewall Configuration

```bash
# UFW (Ubuntu)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 2. Fail2Ban

```bash
sudo apt install fail2ban

# Create jail for Nginx
sudo nano /etc/fail2ban/jail.local
```

```ini
[nginx-http-auth]
enabled = true
filter = nginx-http-auth
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 3
bantime = 3600
```

### 3. Regular Updates

```bash
# Create update script
cat > /opt/robo-trader/update.sh << 'EOF'
#!/bin/bash
cd /opt/robo-trader
git pull
docker-compose build
docker-compose up -d
EOF

chmod +x /opt/robo-trader/update.sh
```

---

## Health Monitoring

### Health Check Script

```bash
cat > /opt/robo-trader/health-check.sh << 'EOF'
#!/bin/bash

# Check if app is responding
if ! curl -sf http://localhost/health > /dev/null; then
    echo "App health check failed!"
    # Restart app
    docker-compose restart app
    # Send alert (configure your alerting)
fi

# Check Redis
if ! docker-compose exec -T redis redis-cli ping > /dev/null; then
    echo "Redis health check failed!"
    docker-compose restart redis
fi

# Check PostgreSQL
if ! docker-compose exec -T postgres pg_isready -U robotrader > /dev/null; then
    echo "PostgreSQL health check failed!"
    docker-compose restart postgres
fi
EOF

chmod +x /opt/robo-trader/health-check.sh

# Run every 5 minutes
echo "*/5 * * * * /opt/robo-trader/health-check.sh" | crontab -
```

---

## Troubleshooting Production Issues

### View Logs

```bash
# All logs
docker-compose logs -f

# Specific service
docker-compose logs -f app

# Last 100 lines
docker-compose logs --tail=100 app
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart app
```

### Check Resources

```bash
# Container stats
docker stats

# Disk usage
docker system df
```

---

## Next Steps

- [Troubleshooting](./10-troubleshooting.md) - Common issues and solutions
