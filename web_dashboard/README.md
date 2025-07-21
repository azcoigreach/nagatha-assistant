# Nagatha Assistant Django Dashboard

A modern Django-based web dashboard for the Nagatha Assistant with Bootstrap 5 integration and modular architecture.

## Features

- **Modern UI**: Clean, responsive design using Bootstrap 5
- **Modular Architecture**: Organized dashboard apps for different features
- **Environment-based Settings**: Separate configurations for development and production
- **Static File Management**: Optimized CSS/JS handling with WhiteNoise
- **Component Library**: Comprehensive Bootstrap component examples
- **Responsive Design**: Mobile-first approach with sidebar navigation
- **Branding**: Custom favicon and Nagatha-themed styling

## Quick Start

### Prerequisites

- Python 3.11+
- Django 4.2+
- Node.js (optional, for npm-based asset management)

### Installation

1. **Navigate to the web dashboard directory:**
   ```bash
   cd web_dashboard
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements-base.txt
   ```

3. **Run migrations:**
   ```bash
   python manage.py migrate
   ```

4. **Collect static files:**
   ```bash
   python manage.py collectstatic --noinput
   ```

5. **Start the development server:**
   ```bash
   python manage.py runserver
   ```

6. **Access the dashboard:**
   Open http://localhost:8000 in your browser

## Project Structure

```
web_dashboard/
├── manage.py                     # Django management script
├── requirements-base.txt         # Basic requirements for base project
├── requirements.txt             # Full requirements including production deps
├── web_dashboard/               # Main project directory
│   ├── __init__.py
│   ├── settings/               # Environment-based settings
│   │   ├── __init__.py
│   │   ├── base.py            # Common settings
│   │   ├── development.py     # Development settings
│   │   └── production.py      # Production settings
│   ├── urls.py                # Main URL configuration
│   ├── wsgi.py               # WSGI application
│   ├── asgi.py               # ASGI application
│   ├── static/               # Project-level static files
│   └── templates/            # Project-level templates
├── dashboard/                  # Main dashboard app
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── migrations/
│   ├── static/dashboard/      # App-specific static files
│   │   ├── css/
│   │   │   └── dashboard.css  # Custom styles
│   │   ├── js/
│   │   │   ├── dashboard.js   # Main dashboard JS
│   │   │   └── chat.js        # Chat functionality
│   │   └── img/
│   │       ├── favicon.svg    # Nagatha favicon
│   │       └── favicon.png    # Fallback favicon
│   └── templates/dashboard/   # Dashboard templates
│       ├── base.html          # Base template with navigation
│       ├── index.html         # Main dashboard page
│       ├── session_detail.html
│       └── components_example.html  # Bootstrap components showcase
└── staticfiles/               # Collected static files (generated)
```

## Settings Configuration

The project uses environment-based settings for better security and deployment flexibility:

### Development Settings
- **File**: `web_dashboard/settings/development.py`
- **Database**: SQLite (simple setup)
- **Debug**: Enabled
- **Security**: Relaxed for development
- **Usage**: Default for local development

### Production Settings
- **File**: `web_dashboard/settings/production.py`
- **Database**: PostgreSQL with environment variables
- **Debug**: Disabled
- **Security**: Enhanced with SSL, HSTS, secure cookies
- **Caching**: Redis integration
- **Task Queue**: Celery with Redis broker

### Environment Variables

Create a `.env` file in the project root:

```env
# Django Configuration
DJANGO_SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com

# Database (Production)
DB_NAME=nagatha_dashboard
DB_USER=nagatha
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=5432

# Redis (Production)
REDIS_HOST=localhost
REDIS_PORT=6379

# Nagatha Integration
OPENAI_API_KEY=your-openai-api-key
NAGATHA_DATABASE_URL=sqlite:///nagatha.db
LOG_LEVEL=INFO

# Security (Production)
SECURE_SSL_REDIRECT=False
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

## Template System

### Base Template (`base.html`)
- Responsive navigation bar with Nagatha branding
- Collapsible sidebar with module navigation
- Bootstrap 5 CDN integration
- Custom CSS and JavaScript inclusion
- Message framework integration
- Footer with status indicators

### Component Structure
- **Navigation**: Top navbar with logo and user menu
- **Sidebar**: Collapsible module navigation
- **Main Content**: Flexible content area
- **Modals**: Example chat interface modal
- **Footer**: Branding and status information

### Available Pages
1. **Dashboard** (`/`): Main overview with system status and chat interface
2. **Components** (`/components/`): Bootstrap 5 component showcase
3. **Health Check** (`/health/`): API endpoint for monitoring

## Static Files

### CSS Structure
- **Bootstrap 5**: CDN-based integration
- **Custom Styles**: `dashboard/static/dashboard/css/dashboard.css`
- **CSS Variables**: Nagatha-themed color palette
- **Responsive Design**: Mobile-first approach
- **Component Styling**: Enhanced Bootstrap components

### JavaScript
- **Bootstrap 5 JS**: CDN-based bundle
- **Dashboard JS**: `dashboard/static/dashboard/js/dashboard.js`
- **Chat JS**: `dashboard/static/dashboard/js/chat.js`
- **Interactive Features**: Sidebar toggle, modal handling

### Images and Icons
- **Favicon**: SVG and PNG versions with Nagatha branding
- **Bootstrap Icons**: CDN-based icon library
- **Custom Graphics**: Scalable vector icons

## Bootstrap 5 Integration

### CDN vs. Local
The project uses CDN delivery for:
- Bootstrap CSS and JavaScript
- Bootstrap Icons
- Faster loading and caching benefits

### Component Usage
The dashboard demonstrates:
- **Layout**: Grid system, containers, responsive utilities
- **Components**: Cards, modals, buttons, forms, alerts
- **Navigation**: Navbar, sidebar, breadcrumbs
- **Utilities**: Spacing, colors, typography, flex

### Customization
- CSS custom properties for theming
- Extended Bootstrap classes
- Nagatha-specific color palette
- Enhanced component styling

## Development Workflow

### Adding New Modules

1. **Create Django App:**
   ```bash
   python manage.py startapp module_name
   ```

2. **Add to INSTALLED_APPS:**
   ```python
   INSTALLED_APPS = [
       # ... existing apps
       'module_name',
   ]
   ```

3. **Create Templates:**
   ```
   module_name/templates/module_name/
   ├── module_base.html
   └── module_index.html
   ```

4. **Add URL Patterns:**
   ```python
   # module_name/urls.py
   urlpatterns = [
       path('', views.ModuleView.as_view(), name='index'),
   ]
   
   # web_dashboard/urls.py
   urlpatterns = [
       path('module/', include('module_name.urls')),
   ]
   ```

5. **Update Sidebar Navigation:**
   Add module link to `dashboard/templates/dashboard/base.html`

### Custom Styling

1. **Add CSS to** `dashboard/static/dashboard/css/dashboard.css`
2. **Use CSS Variables:**
   ```css
   .custom-component {
       background-color: var(--nagatha-primary);
       color: white;
   }
   ```

3. **Follow Bootstrap Patterns:**
   ```css
   .btn-nagatha {
       @extend .btn;
       background-color: var(--nagatha-primary);
   }
   ```

## Deployment

### Development
```bash
python manage.py runserver
```

### Production with Gunicorn
```bash
DJANGO_SETTINGS_MODULE=web_dashboard.settings.production \
gunicorn web_dashboard.wsgi:application
```

### Docker Deployment
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN python manage.py collectstatic --noinput
CMD ["gunicorn", "web_dashboard.wsgi:application"]
```

### Environment Setup
```bash
export DJANGO_SETTINGS_MODULE=web_dashboard.settings.production
export DJANGO_SECRET_KEY=your-production-secret-key
export DEBUG=False
export ALLOWED_HOSTS=yourdomain.com
```

## API Endpoints

- **`GET /`**: Main dashboard
- **`GET /components/`**: Component examples
- **`GET /health/`**: Health check
- **`GET /admin/`**: Django admin interface

## Security Considerations

### Development
- SQLite database (file-based)
- Debug mode enabled
- CORS allows localhost
- Relaxed security settings

### Production
- PostgreSQL database
- Debug mode disabled
- HTTPS enforcement
- Secure cookies and headers
- CORS restricted to allowed origins
- Environment variable based secrets

## Browser Support

- Modern browsers (Chrome 90+, Firefox 88+, Safari 14+)
- Bootstrap 5 compatibility
- Mobile responsive design
- Progressive enhancement approach

## Contributing

1. Follow Django best practices
2. Use Bootstrap components when possible
3. Maintain responsive design
4. Update documentation for new features
5. Test on both development and production settings

## License

This project is part of the Nagatha Assistant suite. See the main project for licensing information.