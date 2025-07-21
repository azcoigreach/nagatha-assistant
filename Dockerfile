# Use Python 3.11 slim as base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Create app user and directories
RUN groupadd -g 1000 app && \
    useradd -u 1000 -g app -m -s /bin/bash app && \
    mkdir -p /app /app/logs /app/staticfiles /app/media && \
    chown -R app:app /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY web_dashboard/requirements.txt /app/
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.txt

# Copy the main Nagatha Assistant source first
COPY src /app/nagatha_src

# Add nagatha_src to Python path in environment
ENV PYTHONPATH="/app/nagatha_src:$PYTHONPATH"

# Copy project files
COPY web_dashboard /app/

# Create necessary directories and set permissions
RUN mkdir -p /app/staticfiles /app/media /app/logs && \
    chown -R app:app /app

# Switch to app user
USER app

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Default command
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "web_dashboard.wsgi:application"]