# Nagatha Dashboard - Docker Infrastructure

This directory contains the Docker infrastructure for the Nagatha Dashboard, a Django-based web interface for the Nagatha Assistant.

## Architecture

The Docker setup includes the following services:

- **web**: Django application serving the dashboard
- **db**: PostgreSQL database for persistent storage
- **redis**: Redis cache and message broker
- **celery**: Background task worker
- **celery-beat**: Scheduled task scheduler
- **nginx**: Reverse proxy and static file server

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Git (to clone the repository)

### Setup

1. **Clone and navigate to the repository:**
   ```bash
   git clone <repository-url>
   cd nagatha-assistant
   ```

2. **Run the quick setup script:**
   ```bash
   ./setup.sh
   ```

3. **Create a superuser:**
   ```bash
   make createsuperuser
   ```

4. **Access the application:**
   - Dashboard: http://localhost/
   - Admin interface: http://localhost/admin/

### Manual Setup

If you prefer manual setup:

1. **Copy and configure environment file:**
   ```bash
   cp .env.docker .env
   # Edit .env with your configuration
   ```

2. **Build and start services:**
   ```bash
   make build
   make up
   ```

3. **Run migrations and collect static files:**
   ```bash
   make migrate
   make collectstatic
   ```

## Configuration

### Environment Variables

Key environment variables to configure in `.env`:

#### Required
- `DJANGO_SECRET_KEY`: Django secret key (generate a secure one)
- `OPENAI_API_KEY`: OpenAI API key for Nagatha functionality
- `DB_PASSWORD`: Database password

#### Optional
- `DEBUG`: Set to `True` for development (default: `False`)
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

### Database Configuration

The default setup uses PostgreSQL with:
- Database: `nagatha_dashboard`
- User: `nagatha`
- Password: Set via `DB_PASSWORD` environment variable

### Redis Configuration

Redis is used for:
- Django caching
- Celery message broker
- Session storage

## Services

### Web Application (Django)

- **Port**: 8000 (internal), 80 (via nginx)
- **Health check**: `/health/`
- **Static files**: Served by nginx
- **Logs**: Available via `make logs-web`

### Database (PostgreSQL)

- **Port**: 5432
- **Persistent storage**: `postgres_data` volume
- **Backups**: Use `make backup-db`
- **Health check**: pg_isready

### Cache/Queue (Redis)

- **Port**: 6379
- **Persistent storage**: `redis_data` volume
- **Memory limit**: 256MB with LRU eviction
- **Health check**: Redis ping

### Background Tasks (Celery)

- **Worker**: Processes background tasks
- **Beat**: Handles scheduled tasks
- **Concurrency**: 2 workers by default
- **Health check**: Celery inspect ping

### Reverse Proxy (Nginx)

- **Port**: 80, 443 (HTTPS ready)
- **Static files**: Cached for 1 year
- **Gzip compression**: Enabled
- **Security headers**: Configured

## Usage

### Common Commands

```bash
# Start all services
make up

# Stop all services
make down

# View logs
make logs

# View specific service logs
make logs-web
make logs-celery
make logs-db

# Restart services
make restart

# Run Django management commands
make migrate
make collectstatic
make createsuperuser
make shell

# Backup and restore
make backup-db
make restore-db BACKUP_FILE=backup.sql

# Health checks
make health
make status

# Complete cleanup
make clean
```

### Development Workflow

1. **Start services:**
   ```bash
   make up
   ```

2. **Make code changes** in the Django application

3. **Restart web service** to see changes:
   ```bash
   make restart-web
   ```

4. **View logs** to debug:
   ```bash
   make logs-web
   ```

## Production Deployment

### SSL/HTTPS Setup

1. **Obtain SSL certificates** (Let's Encrypt recommended)

2. **Update nginx.site.conf** to enable HTTPS server block

3. **Update environment variables:**
   ```bash
   ALLOWED_HOSTS=your-domain.com
   DEBUG=False
   ```

### Performance Tuning

1. **Database optimization:**
   - Increase PostgreSQL shared_buffers
   - Configure connection pooling
   - Set up read replicas if needed

2. **Redis optimization:**
   - Increase memory limit if needed
   - Configure persistence settings

3. **Celery scaling:**
   - Increase worker concurrency
   - Add more worker containers

4. **Nginx optimization:**
   - Enable caching
   - Configure rate limiting
   - Set up load balancing

### Monitoring

1. **Health checks** are configured for all services
2. **Logs** are centralized in `/app/logs/`
3. **Metrics** can be added via Prometheus/Grafana

### Backup Strategy

1. **Database backups:**
   ```bash
   # Daily backup
   make backup-db
   ```

2. **Volume backups:**
   ```bash
   docker run --rm -v nagatha_postgres_data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/postgres_data.tar.gz /data
   ```

## Troubleshooting

### Common Issues

1. **Services won't start:**
   ```bash
   # Check logs
   make logs
   
   # Check service status
   make status
   
   # Verify health
   make health
   ```

2. **Database connection errors:**
   ```bash
   # Check database logs
   make logs-db
   
   # Verify database health
   docker-compose exec db pg_isready -U nagatha
   ```

3. **Static files not loading:**
   ```bash
   # Recollect static files
   make collectstatic
   
   # Check nginx logs
   docker-compose logs nginx
   ```

4. **Celery tasks not processing:**
   ```bash
   # Check celery logs
   make logs-celery
   
   # Inspect celery status
   docker-compose exec celery celery -A web_dashboard inspect stats
   ```

### Debug Mode

To enable debug mode:

1. Set `DEBUG=True` in `.env`
2. Restart services: `make restart`
3. Check logs for detailed error information

### Performance Issues

1. **Monitor resource usage:**
   ```bash
   make monitor
   ```

2. **Check service health:**
   ```bash
   make health
   ```

3. **Scale services if needed:**
   ```bash
   docker-compose up -d --scale celery=3
   ```

## Security Considerations

1. **Change default passwords** in production
2. **Use strong Django secret key**
3. **Configure firewall** to limit access
4. **Enable HTTPS** in production
5. **Regular security updates** of base images
6. **Monitor logs** for suspicious activity

## Contributing

When contributing to the Docker infrastructure:

1. Test changes locally first
2. Update documentation as needed
3. Ensure backward compatibility
4. Add appropriate health checks
5. Update the Makefile if adding new commands

## Support

For issues related to:
- **Docker setup**: Check this documentation and common issues
- **Nagatha Assistant**: See main project documentation
- **Django application**: Check Django logs and documentation