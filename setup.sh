#!/bin/bash

# Quick setup script for Nagatha Dashboard

set -e

echo "🤖 Nagatha Dashboard Quick Setup"
echo "================================"

# Check if Docker and Docker Compose are installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📄 Creating .env file from template..."
    cp .env.docker .env
    echo "⚠️  Please edit .env file and set your configuration values before continuing."
    echo "   Especially important: DJANGO_SECRET_KEY, OPENAI_API_KEY, database passwords"
    read -p "Press Enter when you've updated the .env file..."
fi

# Create backup directory
mkdir -p backups

# Build and start services
echo "🏗️  Building Docker images..."
make build

echo "🚀 Starting services..."
make up

echo "⏳ Waiting for services to be ready..."
sleep 30

# Run migrations
echo "📊 Running database migrations..."
make migrate

# Collect static files
echo "📁 Collecting static files..."
make collectstatic

# Check health
echo "🏥 Checking service health..."
make health

echo ""
echo "✅ Setup completed successfully!"
echo ""
echo "🌐 Your Nagatha Dashboard is now running at:"
echo "   http://localhost"
echo ""
echo "📋 Next steps:"
echo "   1. Create a superuser: make createsuperuser"
echo "   2. Visit http://localhost/admin/ to access Django admin"
echo "   3. Visit http://localhost/ to access the dashboard"
echo ""
echo "🔧 Useful commands:"
echo "   - View logs: make logs"
echo "   - Stop services: make down"
echo "   - Restart services: make restart"
echo "   - See all commands: make help"
echo ""
echo "📚 For more information, see README.md"