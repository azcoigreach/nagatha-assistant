#!/bin/bash
# Celery startup script for Nagatha Assistant
#
# This script starts the Celery worker and beat processes
# for the new Celery-based event system.

set -e

# Change to the project directory
cd "$(dirname "$0")"

# Set up environment
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
export CELERY_BROKER_URL="${CELERY_BROKER_URL:-redis://localhost:6379/0}"
export CELERY_RESULT_BACKEND="${CELERY_RESULT_BACKEND:-redis://localhost:6379/0}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Nagatha Assistant - Celery Startup${NC}"
echo "========================================"

# Check if Redis is running
echo -e "\n${YELLOW}Checking Redis connection...${NC}"
if python -c "import redis; redis.Redis.from_url('${CELERY_BROKER_URL}').ping()" 2>/dev/null; then
    echo -e "${GREEN}✓ Redis is running${NC}"
else
    echo -e "${RED}✗ Redis is not running or not accessible${NC}"
    echo "Please start Redis or check your CELERY_BROKER_URL configuration"
    exit 1
fi

# Function to start Celery worker
start_worker() {
    echo -e "\n${YELLOW}Starting Celery worker...${NC}"
    celery -A nagatha_assistant.celery_app worker \
        --loglevel=info \
        --concurrency=4 \
        --queues=agent,mcp,events,system \
        --hostname=nagatha-worker@%h \
        &
    WORKER_PID=$!
    echo -e "${GREEN}✓ Celery worker started (PID: $WORKER_PID)${NC}"
}

# Function to start Celery beat
start_beat() {
    echo -e "\n${YELLOW}Starting Celery beat...${NC}"
    celery -A nagatha_assistant.celery_app beat \
        --loglevel=info \
        --schedule=/tmp/celerybeat-schedule \
        &
    BEAT_PID=$!
    echo -e "${GREEN}✓ Celery beat started (PID: $BEAT_PID)${NC}"
}

# Function to start Celery flower (monitoring)
start_flower() {
    echo -e "\n${YELLOW}Starting Celery flower (monitoring)...${NC}"
    celery -A nagatha_assistant.celery_app flower \
        --port=5555 \
        &
    FLOWER_PID=$!
    echo -e "${GREEN}✓ Celery flower started (PID: $FLOWER_PID) - http://localhost:5555${NC}"
}

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Shutting down Celery processes...${NC}"
    
    if [ ! -z "$WORKER_PID" ]; then
        kill $WORKER_PID 2>/dev/null || true
        echo -e "${GREEN}✓ Worker stopped${NC}"
    fi
    
    if [ ! -z "$BEAT_PID" ]; then
        kill $BEAT_PID 2>/dev/null || true
        echo -e "${GREEN}✓ Beat stopped${NC}"
    fi
    
    if [ ! -z "$FLOWER_PID" ]; then
        kill $FLOWER_PID 2>/dev/null || true
        echo -e "${GREEN}✓ Flower stopped${NC}"
    fi
    
    echo -e "${BLUE}Celery shutdown complete${NC}"
    exit 0
}

# Set up signal handling
trap cleanup SIGINT SIGTERM

# Parse command line arguments
case "${1:-all}" in
    "worker")
        start_worker
        echo -e "\n${GREEN}Celery worker is running. Press Ctrl+C to stop.${NC}"
        wait $WORKER_PID
        ;;
    "beat")
        start_beat
        echo -e "\n${GREEN}Celery beat is running. Press Ctrl+C to stop.${NC}"
        wait $BEAT_PID
        ;;
    "flower")
        start_flower
        echo -e "\n${GREEN}Celery flower is running. Press Ctrl+C to stop.${NC}"
        wait $FLOWER_PID
        ;;
    "all"|"")
        start_worker
        sleep 2
        start_beat
        sleep 2
        start_flower
        
        echo -e "\n${GREEN}All Celery processes are running:${NC}"
        echo "  - Worker: handling tasks"
        echo "  - Beat: scheduling periodic tasks"
        echo "  - Flower: monitoring at http://localhost:5555"
        echo -e "\n${YELLOW}Press Ctrl+C to stop all processes${NC}"
        
        # Wait for any process to exit
        wait
        ;;
    "test")
        echo -e "\n${YELLOW}Running Celery integration test...${NC}"
        python test_celery_integration.py
        ;;
    *)
        echo "Usage: $0 [worker|beat|flower|all|test]"
        echo ""
        echo "Commands:"
        echo "  worker  - Start only the Celery worker"
        echo "  beat    - Start only the Celery beat scheduler"
        echo "  flower  - Start only the Celery flower monitoring"
        echo "  all     - Start worker, beat, and flower (default)"
        echo "  test    - Run the Celery integration test"
        exit 1
        ;;
esac