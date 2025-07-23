# Nagatha Assistant - Celery Deployment Quick Start

## Overview

This guide provides a quick start for deploying the new Celery-based event system in Nagatha Assistant.

## Prerequisites

1. **Redis Server** (required for Celery broker and result backend)
2. **Python 3.11+** with pip
3. **Git** for cloning the repository

## Installation Steps

### 1. Install Dependencies

```bash
# Install Redis (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install redis-server

# Start Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy environment configuration
cp .env.example.celery .env

# Edit configuration
nano .env
```

Required settings in `.env`:
```bash
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Test Installation

```bash
# Run basic tests (no Celery required)
./test_basic_integration.py

# Run full integration tests (requires Redis)
./test_celery_integration.py
```

### 4. Start Services

```bash
# Start all Celery services (worker, beat, monitoring)
./start_celery.sh

# Or start individual services:
./start_celery.sh worker    # Task processing
./start_celery.sh beat      # Scheduled tasks
./start_celery.sh flower    # Web monitoring (http://localhost:5555)
```

### 5. Use the System

The system maintains backward compatibility. Existing code will automatically use Celery when available, falling back to the original system if not.

```python
# Agent operations (automatically uses Celery)
from nagatha_assistant.core.agent import send_message_via_celery, start_session

session_id = await start_session()
response = await send_message_via_celery(session_id, "Hello!")

# Event system (automatically uses Celery)
from nagatha_assistant.core.celery_storage import get_event_bus
event_bus = get_event_bus()
```

## Production Deployment

### Using Docker

```dockerfile
# Add to your Dockerfile
RUN pip install celery redis
EXPOSE 5555

# Start script
CMD ["./start_celery.sh"]
```

### Using systemd

Create service files for production:

```ini
# /etc/systemd/system/nagatha-celery-worker.service
[Unit]
Description=Nagatha Celery Worker
After=redis.service

[Service]
Type=forking
User=nagatha
WorkingDirectory=/opt/nagatha-assistant
ExecStart=/opt/nagatha-assistant/start_celery.sh worker
Restart=always

[Install]
WantedBy=multi-user.target
```

### Environment Variables

Production environment variables:
```bash
# High availability Redis
CELERY_BROKER_URL=redis://redis-cluster:6379/0

# Production settings
CELERY_WORKER_CONCURRENCY=8
CELERY_TASK_SOFT_TIME_LIMIT=600
CELERY_TASK_TIME_LIMIT=1200

# Monitoring
CELERY_FLOWER_PORT=5555
CELERY_FLOWER_AUTH=admin:secure_password
```

## Monitoring

- **Celery Flower**: http://localhost:5555 - Real-time task monitoring
- **Redis CLI**: `redis-cli monitor` - Redis operation monitoring  
- **Logs**: Check worker logs for task execution details

## Troubleshooting

### Common Issues

1. **"No module named 'celery'"**
   ```bash
   pip install celery redis
   ```

2. **"Redis connection failed"**
   ```bash
   sudo systemctl start redis-server
   redis-cli ping  # Should return PONG
   ```

3. **"No workers available"**
   ```bash
   ./start_celery.sh worker
   ```

4. **Tasks not executing**
   - Check Redis connectivity
   - Verify worker is running
   - Check task routing configuration

### Health Checks

```bash
# Check Redis
redis-cli ping

# Check Celery worker
celery -A nagatha_assistant.celery_app inspect active

# Check task queues
celery -A nagatha_assistant.celery_app inspect reserved

# Run integration tests
./test_celery_integration.py
```

## Migration Strategy

The system supports gradual migration:

1. **Phase 1**: Deploy with existing code (automatic fallback)
2. **Phase 2**: Update high-traffic operations to use Celery explicitly
3. **Phase 3**: Monitor performance and scale workers as needed
4. **Phase 4**: Optimize task distribution and add custom queues

## Support

- **Documentation**: See `CELERY_INTEGRATION.md` for detailed documentation
- **Tests**: Run `./test_basic_integration.py` for quick validation
- **Monitoring**: Use Celery Flower for real-time monitoring
- **Logs**: Check worker logs for debugging information

## Next Steps

After deployment:

1. Monitor task execution performance
2. Adjust worker concurrency based on load
3. Set up alerting for failed tasks
4. Consider Redis clustering for high availability
5. Implement custom task routing for specific workloads