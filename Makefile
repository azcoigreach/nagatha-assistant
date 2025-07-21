# Makefile for Nagatha Dashboard Docker management

.PHONY: help build up down logs restart clean migrate collectstatic shell test backup restore

# Default environment file
ENV_FILE ?= .env.docker

help: ## Show this help message
	@echo "Nagatha Dashboard Docker Management"
	@echo "=================================="
	@echo ""
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

build: ## Build the Docker images
	docker compose --env-file $(ENV_FILE) build

up: ## Start all services
	docker compose --env-file $(ENV_FILE) up -d

down: ## Stop all services
	docker compose --env-file $(ENV_FILE) down

logs: ## Show logs for all services
	docker compose --env-file $(ENV_FILE) logs -f

logs-web: ## Show logs for web service only
	docker compose --env-file $(ENV_FILE) logs -f web

logs-celery: ## Show logs for celery service only
	docker compose --env-file $(ENV_FILE) logs -f celery

logs-db: ## Show logs for database service only
	docker compose --env-file $(ENV_FILE) logs -f db

restart: ## Restart all services
	docker compose --env-file $(ENV_FILE) restart

restart-web: ## Restart web service only
	docker compose --env-file $(ENV_FILE) restart web

restart-celery: ## Restart celery services
	docker compose --env-file $(ENV_FILE) restart celery celery-beat

clean: ## Remove all containers, networks, and volumes
	docker compose --env-file $(ENV_FILE) down -v --remove-orphans
	docker system prune -f

migrate: ## Run Django migrations
	docker compose --env-file $(ENV_FILE) exec web python manage.py migrate

makemigrations: ## Create Django migrations
	docker compose --env-file $(ENV_FILE) exec web python manage.py makemigrations

collectstatic: ## Collect static files
	docker compose --env-file $(ENV_FILE) exec web python manage.py collectstatic --noinput

shell: ## Open Django shell
	docker compose --env-file $(ENV_FILE) exec web python manage.py shell

shell-db: ## Open database shell
	docker compose --env-file $(ENV_FILE) exec web python manage.py dbshell

createsuperuser: ## Create Django superuser
	docker compose --env-file $(ENV_FILE) exec web python manage.py createsuperuser

test: ## Run Django tests
	docker compose --env-file $(ENV_FILE) exec web python manage.py test

test-coverage: ## Run tests with coverage
	docker compose --env-file $(ENV_FILE) exec web coverage run --source='.' manage.py test
	docker compose --env-file $(ENV_FILE) exec web coverage report

backup-db: ## Backup database
	@echo "Creating database backup..."
	docker compose --env-file $(ENV_FILE) exec db pg_dump -U nagatha nagatha_dashboard > backups/nagatha_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "Backup completed: backups/nagatha_$(shell date +%Y%m%d_%H%M%S).sql"

restore-db: ## Restore database from backup (usage: make restore-db BACKUP_FILE=backup.sql)
	@if [ -z "$(BACKUP_FILE)" ]; then echo "Usage: make restore-db BACKUP_FILE=backup.sql"; exit 1; fi
	@echo "Restoring database from $(BACKUP_FILE)..."
	docker compose --env-file $(ENV_FILE) exec -T db psql -U nagatha -d nagatha_dashboard < $(BACKUP_FILE)
	@echo "Database restored successfully"

setup: ## Initial setup - build, run migrations, create superuser
	make build
	make up
	@echo "Waiting for services to start..."
	sleep 30
	make migrate
	make collectstatic
	@echo "Setup completed! You can now create a superuser with 'make createsuperuser'"

dev-setup: ## Setup for development with sample data
	make setup
	make createsuperuser
	@echo "Development setup completed!"

status: ## Show status of all services
	docker compose --env-file $(ENV_FILE) ps

health: ## Check health of all services
	@echo "Checking service health..."
	@docker compose --env-file $(ENV_FILE) exec web curl -f http://localhost:8000/health/ && echo "✓ Web service healthy" || echo "✗ Web service unhealthy"
	@docker compose --env-file $(ENV_FILE) exec db pg_isready -U nagatha -d nagatha_dashboard && echo "✓ Database healthy" || echo "✗ Database unhealthy"
	@docker compose --env-file $(ENV_FILE) exec redis redis-cli ping && echo "✓ Redis healthy" || echo "✗ Redis unhealthy"

update: ## Update and restart services
	git pull
	make build
	make down
	make up
	make migrate
	make collectstatic

# Production commands
prod-deploy: ## Deploy to production (use with ENV_FILE=.env.production)
	@if [ "$(ENV_FILE)" = ".env.docker" ]; then echo "Warning: Using development environment file. Set ENV_FILE=.env.production for production deployment."; fi
	make build
	make down
	make up
	make migrate
	make collectstatic

prod-backup: ## Create production backup
	mkdir -p backups
	make backup-db

# Monitoring and debugging
monitor: ## Monitor resource usage
	docker stats

inspect-web: ## Inspect web container
	docker compose --env-file $(ENV_FILE) exec web /bin/bash

inspect-db: ## Inspect database container
	docker compose --env-file $(ENV_FILE) exec db /bin/bash

# Clean up commands
clean-images: ## Remove unused Docker images
	docker image prune -f

clean-volumes: ## Remove unused Docker volumes
	docker volume prune -f

clean-all: ## Remove all unused Docker resources
	docker system prune -a --volumes -f

# Development helpers
dev-logs: ## Show development logs with timestamps
	docker compose --env-file $(ENV_FILE) logs -f --timestamps

dev-reset: ## Reset development environment completely
	make clean
	make dev-setup