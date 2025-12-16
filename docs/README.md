# Robo Trader Documentation

Welcome to the Robo Trader documentation. This guide covers everything you need to know to set up, configure, and run the ML-based cryptocurrency trading bot.

## Table of Contents

1. [Overview](./01-overview.md) - Architecture and features
2. [Installation](./02-installation.md) - Setup instructions
3. [Configuration](./03-configuration.md) - Configuration files and options
4. [Services & Ports](./04-services-ports.md) - All services and their ports
5. [Docker Guide](./05-docker-guide.md) - Docker commands and deployment
6. [CLI Reference](./06-cli-reference.md) - Command line interface
7. [API Reference](./07-api-reference.md) - REST API endpoints
8. [Trading Strategies](./08-trading-strategies.md) - ML models and strategies
9. [Deployment](./09-deployment.md) - Production deployment guide
10. [Troubleshooting](./10-troubleshooting.md) - Common issues and solutions

## Quick Start

```bash
# Clone and setup
cd robo-trader
cp .env.production .env
# Edit .env with your API keys

# Option 1: Docker (Recommended)
docker-compose up -d
# Access at: http://localhost

# Option 2: Manual
pip install -r requirements.txt
python main.py web
# Access at: http://localhost:8000
```

## Support

For issues and feature requests, please open an issue on the repository.
