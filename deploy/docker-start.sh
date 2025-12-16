#!/bin/bash
# Docker Compose Management Script

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

COMPOSE_FILE="docker-compose.yml"
PROJECT_NAME="robo-trader"

print_header() {
    echo ""
    echo -e "${BLUE}=========================================="
    echo "   Robo Trader - Docker Management"
    echo -e "==========================================${NC}"
    echo ""
}

print_usage() {
    echo "Usage: $0 {start|stop|restart|logs|status|build|clean|shell}"
    echo ""
    echo "Commands:"
    echo "  start     - Start all services"
    echo "  stop      - Stop all services"
    echo "  restart   - Restart all services"
    echo "  logs      - View logs (use: logs [service])"
    echo "  status    - Show service status"
    echo "  build     - Build/rebuild images"
    echo "  clean     - Remove containers and volumes"
    echo "  shell     - Open shell in app container"
    echo "  monitor   - Start with monitoring stack"
    echo ""
}

start() {
    echo -e "${GREEN}Starting services...${NC}"
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d
    echo -e "${GREEN}Services started successfully!${NC}"
    echo ""
    echo "Access the dashboard at: http://localhost"
    status
}

start_with_monitoring() {
    echo -e "${GREEN}Starting services with monitoring...${NC}"
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME --profile monitoring up -d
    echo -e "${GREEN}Services started with monitoring!${NC}"
    echo ""
    echo "Dashboard: http://localhost"
    echo "Prometheus: http://localhost:9090"
    echo "Grafana: http://localhost:3000"
}

stop() {
    echo -e "${YELLOW}Stopping services...${NC}"
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME down
    echo -e "${GREEN}Services stopped${NC}"
}

restart() {
    echo -e "${YELLOW}Restarting services...${NC}"
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME restart
    echo -e "${GREEN}Services restarted${NC}"
}

logs() {
    if [ -z "$2" ]; then
        docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME logs -f --tail=100
    else
        docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME logs -f --tail=100 $2
    fi
}

status() {
    echo ""
    echo -e "${BLUE}Service Status:${NC}"
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME ps
    echo ""
    echo -e "${BLUE}Resource Usage:${NC}"
    docker stats --no-stream $(docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME ps -q) 2>/dev/null || true
}

build() {
    echo -e "${GREEN}Building images...${NC}"
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME build --no-cache
    echo -e "${GREEN}Build complete${NC}"
}

clean() {
    echo -e "${RED}WARNING: This will remove all containers and volumes!${NC}"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME down -v --remove-orphans
        docker system prune -f
        echo -e "${GREEN}Cleanup complete${NC}"
    fi
}

shell() {
    echo -e "${GREEN}Opening shell in app container...${NC}"
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME exec app /bin/bash
}

# Main
print_header

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    logs)
        logs "$@"
        ;;
    status)
        status
        ;;
    build)
        build
        ;;
    clean)
        clean
        ;;
    shell)
        shell
        ;;
    monitor)
        start_with_monitoring
        ;;
    *)
        print_usage
        exit 1
        ;;
esac
