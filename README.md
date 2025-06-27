# THINK eLearn

A modern eLearning platform built with Django and Wagtail CMS, designed for scalable content management and educational delivery.

## Overview

THINK eLearn is a comprehensive eLearning website platform that combines Django's robust backend capabilities with Wagtail's intuitive content management system. The platform features a modern, responsive design built with Tailwind CSS and is optimized for deployment on Railway.

## Tech Stack

- **Backend**: Django 5.2.3 with Wagtail 7.0.1 CMS
- **Database**: SQLite (development), PostgreSQL (production)
- **Frontend**: Tailwind CSS with custom design system
- **Fonts**: Inter (body), Poppins (headings)
- **Deployment**: Railway with Docker containerization
- **Package Management**: uv for Python dependencies, npm for Node.js

## Features

- **Content Management**: Flexible page creation and editing via Wagtail admin
- **Responsive Design**: Mobile-first approach with Tailwind CSS
- **Search Functionality**: Built-in Wagtail search capabilities
- **SEO Optimized**: Meta tags, structured data, and SEO fields
- **Planned Modules**:
  - Blog system for content marketing
  - Portfolio showcase for projects and case studies
  - Contact forms with email handling
  - Service pages for offerings

## Project Structure

```text
thinkelearn/
├── thinkelearn/           # Main Django project
│   ├── settings/          # Split settings configuration
│   │   ├── base.py        # Shared settings
│   │   ├── dev.py         # Development settings
│   │   └── production.py  # Production settings
│   ├── static/            # Static files
│   └── templates/         # Base templates
├── home/                  # Homepage app
├── search/                # Search functionality
├── docs/                  # Project documentation
├── requirements.txt       # Python dependencies (Docker)
├── pyproject.toml         # uv project configuration
├── tailwind.config.js     # Tailwind CSS configuration
└── manage.py              # Django management script
```

## Prerequisites

### Traditional Setup

- Python 3.13+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/) package manager

### Docker Setup (Recommended)

- Docker and Docker Compose

## Installation & Setup

### Option 1: Docker Development (Recommended)

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd thinkelearn
   ```

2. **Start the development environment**

   ```bash
   # Start all services
   docker-compose up

   # Start with CSS watching (for frontend development)
   docker-compose --profile css up
   ```

3. **Run initial setup**

   ```bash
   # Run migrations
   docker-compose exec web python manage.py migrate

   # Create superuser
   docker-compose exec web python manage.py createsuperuser

   # Collect static files (if needed)
   docker-compose exec web python manage.py collectstatic
   ```

4. **Access the application**
   - Website: <http://localhost:8000>
   - Admin: <http://localhost:8000/admin/>
   - Django Admin: <http://localhost:8000/django-admin/>
   - PgAdmin: <http://localhost:5050> (Email: `admin@thinkelearn.local`, Password: `admin`)

### Option 2: Traditional Setup

1. **Clone and setup environment**

   ```bash
   git clone <repository-url>
   cd thinkelearn

   # Install Python dependencies
   uv sync

   # Install Node.js dependencies
   npm install
   ```

2. **Database setup**

   ```bash
   # Run migrations
   uv run python manage.py migrate

   # Create superuser
   uv run python manage.py createsuperuser
   ```

3. **Start development servers**

   ```bash
   # Terminal 1: Django development server
   uv run python manage.py runserver

   # Terminal 2: Tailwind CSS watcher
   npm run build-css
   ```

## Development

### Docker Commands

```bash
# Start/stop services
docker-compose up -d                    # Start in background
docker-compose down                     # Stop services
docker-compose down -v                  # Stop and remove volumes

# Django management
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py collectstatic
docker-compose exec web python manage.py shell

# Database access
docker-compose exec db psql -U postgres -d thinkelearn

# View logs
docker-compose logs -f web              # Django logs
docker-compose logs -f db               # Database logs
docker-compose logs -f pgadmin          # PgAdmin logs
```

### Traditional Commands

```bash
# Django management
uv run python manage.py runserver       # Start development server
uv run python manage.py migrate         # Run migrations
uv run python manage.py makemigrations  # Create migrations
uv run python manage.py createsuperuser # Create admin user
uv run python manage.py collectstatic   # Collect static files

# CSS compilation
npm run build-css                       # Development with watch mode
npm run build-css-prod                  # Production build with minification

# Dependencies
uv sync                                 # Install Python dependencies
uv add <package-name>                   # Add new Python package
npm install                             # Install Node.js dependencies
```

## Environment Configuration

### Development

- **Settings**: `thinkelearn.settings.dev`
- **Database**: PostgreSQL (default) or SQLite (fallback for traditional setup)
- **Debug**: Enabled
- **Email**: Console backend

### Production

- **Settings**: `thinkelearn.settings.production`
- **Database**: PostgreSQL via Railway
- **Debug**: Disabled
- **Static Files**: Served via whitenoise

## Deployment

The application is configured for deployment on Railway:

1. **Build Process**: Uses production Dockerfile
2. **Database**: Managed PostgreSQL service
3. **Static Files**: Collected and served via whitenoise
4. **CSS**: Built with minification during Docker build

### Manual Deployment Steps

```bash
# Build production CSS
npm run build-css-prod

# Collect static files
python manage.py collectstatic --noinput

# Run migrations (handled automatically by Railway)
python manage.py migrate
```

## URL Structure

- `/` - Homepage
- `/admin/` - Wagtail admin interface
- `/django-admin/` - Django admin interface
- `/search/` - Search functionality
- `/documents/` - Document serving
- Future routes: `/blog/`, `/portfolio/`, `/contact/`

## Contributing

1. **Development Environment**: Use Docker setup for consistency
2. **Code Style**: Follow Django conventions and existing patterns
3. **CSS**: Use Tailwind utilities, follow the design system
4. **Database**: Always create and test migrations
5. **Testing**: Ensure functionality works in both development and production settings

## License

[License information to be added]

---

For detailed development guidance and architectural decisions, see [CLAUDE.md](CLAUDE.md).
