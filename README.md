# THINK eLearn

A modern eLearning platform built with Django and Wagtail CMS, featuring comprehensive CI/CD automation and scalable deployment architecture.

![CI Status](https://github.com/think-elearn/thinkelearn/workflows/CI%20Pipeline/badge.svg)
![Coverage](https://img.shields.io/badge/coverage-80%25-brightgreen)
![Python](https://img.shields.io/badge/python-3.13-blue)
![Django](https://img.shields.io/badge/django-5.2.3-green)

## Overview

THINK eLearn is a comprehensive eLearning website platform that combines Django's robust backend capabilities with Wagtail's intuitive content management system. The platform features a modern, responsive design built with Tailwind CSS, comprehensive test coverage, automated CI/CD pipelines, and is optimized for deployment on Railway.

## Tech Stack

### Core Technologies
- **Backend**: Django 5.2.3 with Wagtail 7.0.1 CMS
- **Database**: SQLite (development), PostgreSQL (production/CI)
- **Frontend**: Tailwind CSS with custom design system
- **Fonts**: Inter (body), Poppins (headings)
- **Package Management**: uv for Python dependencies, npm for Node.js

### DevOps & CI/CD
- **Testing**: pytest with 120+ comprehensive tests, 80%+ coverage
- **Code Quality**: ruff (linting/formatting), mypy (type checking)
- **Security**: safety (vulnerability scanning), bandit (security linting)
- **CI**: GitHub Actions with parallel test execution
- **Deployment**: Railway with nixpacks (replacing Docker)
- **Monitoring**: Automated health checks and error tracking

## Features

### Core Platform
- **Content Management**: Flexible page creation and editing via Wagtail admin
- **Responsive Design**: Mobile-first approach with Tailwind CSS
- **Search Functionality**: Built-in Wagtail search capabilities
- **SEO Optimized**: Meta tags, structured data, and SEO fields

### Content Modules
- **Homepage**: Hero sections, features, testimonials with StreamFields
- **About Page**: Company story, team members, values, timeline
- **Contact System**: Advanced forms with email handling and FAQ sections
- **Blog System**: Content marketing with categories, tags, and related posts
- **Portfolio**: Project showcases with case studies and metrics
- **Communications**: Twilio SMS/voicemail integration with admin workflow

### DevOps & Quality Assurance
- **Comprehensive Testing**: 120+ tests covering models, views, forms, and integrations
- **Automated CI/CD**: GitHub Actions pipeline with parallel job execution
- **Code Quality**: Automated linting, formatting, and type checking
- **Security**: Vulnerability scanning and security linting
- **Performance**: CSS optimization, static file compression, database optimization

## Project Structure

```text
thinkelearn/
├── .github/workflows/     # CI/CD automation
│   └── ci.yml            # GitHub Actions pipeline
├── thinkelearn/          # Main Django project
│   ├── settings/         # Split settings configuration
│   │   ├── base.py       # Shared settings
│   │   ├── dev.py        # Development settings
│   │   ├── production.py # Production settings
│   │   └── test.py       # Testing settings
│   ├── static/           # Static files
│   └── templates/        # Base templates
├── home/                 # Homepage and core pages
│   ├── models.py         # Page models (HomePage, AboutPage, etc.)
│   ├── tests/            # Comprehensive test suite
│   └── management/       # Setup commands
├── blog/                 # Blog system
│   ├── models.py         # BlogPage, categories, tags
│   └── tests/            # Blog functionality tests
├── communications/       # Twilio SMS/voicemail
│   ├── models.py         # Message handling
│   ├── views.py          # Webhook endpoints
│   └── tests/            # Integration tests
├── search/               # Search functionality
├── docs/                 # Project documentation
│   ├── ci-cd-plan.md     # Complete CI/CD implementation plan
│   └── ...               # Other planning documents
├── scripts/              # Automation scripts
│   └── setup-ci-cd.sh   # CI/CD environment setup
├── pyproject.toml        # Dependencies and tool configuration (includes pytest)
├── nixpacks.toml         # Railway deployment config
├── railway.toml          # Railway service settings
├── tailwind.config.js    # CSS configuration
└── conftest.py           # Shared test fixtures
```

## Prerequisites

### Quick Start (Recommended)

- **Docker and Docker Compose** for development environment
- **Git** for version control

### Traditional Setup

- **Python 3.13+** with [uv](https://docs.astral.sh/uv/) package manager
- **Node.js 20+** for CSS builds
- **PostgreSQL** (optional, SQLite used by default)

### CI/CD Development

- All of the above, plus:
- **pytest** for testing framework
- **ruff** for code quality
- **GitHub account** for CI/CD integration
- **Railway account** for deployment

## Installation & Setup

### Option 1: Docker Development (Recommended)

1. **Clone the repository**

   ```bash
   git clone <https://github.com/think-elearn/thinkelearn>
   cd thinkelearn
   ```

2. **Start the development environment**

   ```bash
   # Option A: Complete setup (recommended for first time)
   ./start.sh setup

   # Option B: Basic start (containers + migrations only)
   ./start.sh

   # Option C: Manual docker-compose (requires manual setup)
   docker-compose --profile css up
   ```

3. **Admin access** (after setup)
   - If you used `./start.sh setup`: Login with `admin` / `defaultpassword123`
   - If you used basic start: Create admin manually:

     ```bash
     docker-compose exec web python manage.py createsuperuser
     ```

4. **Access the application**
   - Website: <http://localhost:8000>
   - **Wagtail Admin** (CMS): <http://localhost:8000/admin/> - Content management, pages, documents
   - **Django Admin** (System): <http://localhost:8000/django-admin/> - User management, communications, system data
   - **Mailpit** (Email testing): <http://localhost:8025> - View email notifications
   - **pgAdmin** (Database): <http://localhost:5050> (Email: `admin@thinkelearn.com`, Password: `admin`)

### Option 2: Traditional Setup

1. **Clone and setup environment**

   ```bash
   git clone <https://github.com/think-elearn/thinkelearn>
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

### Container Management Script

The project includes a comprehensive `start.sh` script for easy container management:

```bash
# Start development environment (containers + migrations)
./start.sh

# Complete setup (containers + migrations + admin + pages)
./start.sh setup

# Stop all containers
./start.sh stop

# Stop containers and clean up resources (preserves database)
./start.sh reset

# Stop containers and clean up everything (⚠️ REMOVES DATABASE)
./start.sh clean

# Full rebuild and restart (includes automatic migrations)
./start.sh rebuild

# Show container status
./start.sh status

# View logs from all containers
./start.sh logs

# Show help
./start.sh help
```

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

### pgAdmin Setup

pgAdmin is included in the Docker setup for easy database management and inspection.

#### Accessing pgAdmin

1. **Start the services**: `docker-compose up`
2. **Open pgAdmin**: Navigate to <http://localhost:5050>
3. **Login credentials**:
   - Email: `admin@thinkelearn.com`
   - Password: `admin`

#### Connecting to PostgreSQL Database

Once logged into pgAdmin:

1. **Add New Server**:
   - Right-click "Servers" → "Register" → "Server..."

2. **General Tab**:
   - Name: `THINK eLearn Dev` (or any descriptive name)

3. **Connection Tab**:
   - Host name/address: `db`
   - Port: `5432`
   - Maintenance database: `thinkelearn`
   - Username: `postgres`
   - Password: `postgres`

4. **Save**: Click "Save" to establish the connection

#### Common pgAdmin Tasks

```sql
-- View all tables
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public';

-- Check Django migrations
SELECT * FROM django_migrations ORDER BY applied DESC;

-- View Wagtail pages
SELECT id, title, slug, path FROM wagtailcore_page;

-- Check user accounts
SELECT id, username, email, is_active, is_superuser, date_joined
FROM auth_user;
```

#### Troubleshooting pgAdmin

- **Connection refused**: Ensure database service is running (`docker-compose up db`)
- **Login issues**: Use exact credentials: `admin@thinkelearn.com` / `admin`
- **Host not found**: Use `db` as hostname (Docker service name), not `localhost`
- **Port conflicts**: If port 5050 is in use, modify docker-compose.yml ports mapping

### Testing & Quality Assurance

The project includes a comprehensive test suite and code quality tools:

```bash
# Quick setup for CI/CD development
./scripts/setup-ci-cd.sh              # Automated CI/CD environment setup

# Testing
pytest                                 # Run all tests
pytest --cov                          # Run tests with coverage report
pytest --cov --cov-report=html        # Generate HTML coverage report
pytest home/tests/                     # Run specific app tests
python manage.py test --settings=thinkelearn.settings.test  # Django test runner

# Code Quality
uv run ruff check .                    # Lint code
uv run ruff format .                   # Format code
uv run mypy .                          # Type checking

# Security
uv run safety check                    # Check for known vulnerabilities
uv run bandit -r .                     # Security linting

# Development Dependencies
uv sync --group dev                    # Install development tools
uv sync --group test                   # Install testing tools
uv sync --group security               # Install security tools
```

### Traditional Commands

```bash
# Django management
uv run python manage.py runserver       # Start development server
uv run python manage.py migrate         # Run migrations
uv run python manage.py makemigrations  # Create migrations
uv run python manage.py createsuperuser # Create admin user
uv run python manage.py collectstatic   # Collect static files

# Special setup commands
uv run python manage.py create_admin    # Create admin with environment variables
uv run python manage.py setup_pages     # Create initial page structure

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

## CI/CD Pipeline

### Continuous Integration

The project uses **GitHub Actions** for automated testing and quality assurance:

- **Automated Testing**: 120+ tests run on every push and pull request
- **Code Quality**: Linting, formatting, and type checking
- **Security Scanning**: Vulnerability and security analysis
- **Build Verification**: CSS compilation and static file generation
- **Multi-environment**: Tests run against PostgreSQL (production-like)

**Workflow Triggers**: Push to `main`/`develop`, all pull requests

### Continuous Deployment

**Railway Integration** provides automated deployment:

1. **Source Control**: Automatic deployments from GitHub `main` branch
2. **Build Process**: nixpacks replaces Docker for faster, more efficient builds
3. **Database**: Automatic migrations and managed PostgreSQL
4. **Static Files**: CSS compilation and static file collection
5. **Health Checks**: Automated deployment verification
6. **Rollback**: Quick rollback capabilities for failed deployments

### Deployment Environments

- **Development**: Docker Compose for local development
- **CI Testing**: GitHub Actions with PostgreSQL services
- **Staging**: Railway staging environment (optional)
- **Production**: Railway production with managed database

## Deployment

### Automated Deployment (Recommended)

The application is configured for zero-downtime deployment on Railway:

1. **Push to GitHub**: Changes to `main` branch trigger automatic deployment
2. **CI Validation**: GitHub Actions validates code quality and tests
3. **Build Process**: nixpacks builds application with CSS compilation
4. **Database Migration**: Automatic migration execution
5. **Health Checks**: Deployment verification and monitoring

### Manual Deployment Steps

For manual deployments or troubleshooting:

```bash
# Build production CSS
npm run build-css-prod

# Collect static files
python manage.py collectstatic --noinput

# Run migrations (handled automatically by Railway)
python manage.py migrate

# Deploy via Railway CLI
railway login
railway link [project-id]
railway up
```

### Environment Variables

Required for production deployment:

```bash
# Core Django settings
SECRET_KEY=your-secret-key
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DJANGO_SETTINGS_MODULE=thinkelearn.settings.production

# Database (automatically set by Railway)
DATABASE_URL=postgresql://...

# Email settings (optional)
DEFAULT_FROM_EMAIL=noreply@yourdomain.com

# Twilio integration (optional)
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_PHONE_NUMBER=your-twilio-number
VOICEMAIL_NOTIFICATION_EMAILS=admin@yourdomain.com
SMS_NOTIFICATION_EMAILS=admin@yourdomain.com
```

## URL Structure

- `/` - Homepage
- `/admin/` - **Wagtail Admin** - Content management, pages, documents, media
- `/django-admin/` - **Django Admin** - User management, communications, system administration
- `/search/` - Search functionality
- `/documents/` - Document serving
- `/communications/` - Twilio webhook endpoints and recording access
- Future routes: `/blog/`, `/portfolio/`, `/contact/`

## Admin Interfaces

The platform uses two distinct admin interfaces:

### Wagtail Admin (`/admin/`)

**Purpose**: Content Management System

- **Content creators and editors** use this interface
- Manage pages, blog posts, images, documents
- User-friendly visual editor with drag-and-drop
- SEO settings, page publishing workflow
- Media library management

### Django Admin (`/django-admin/`)

**Purpose**: System Administration

- **Administrators and technical staff** use this interface
- User and group management
- **Communications management** (voicemails, SMS)
- System settings and configuration
- Technical data and logs
- Raw database access when needed

### Access Control

- Same user accounts work for both admin interfaces
- Different permission levels can be assigned
- Content editors typically only need Wagtail admin access
- System administrators need access to both interfaces

## Contributing

### Development Workflow

1. **Setup**: Use `./scripts/setup-ci-cd.sh` for complete environment setup
2. **Development**: Use Docker Compose (`./start.sh`) for consistent environment
3. **Testing**: Run `pytest --cov` before committing changes
4. **Code Quality**: Use `ruff check` and `ruff format` for code standards
5. **Security**: Run `safety check` and `bandit` for security validation

### Code Standards

- **Python**: Follow PEP 8, use type hints, maintain 80%+ test coverage
- **Django**: Follow Django conventions, use proper model relationships
- **CSS**: Use Tailwind utilities, follow the established design system
- **JavaScript**: Minimal usage, prefer server-side rendering
- **Testing**: Write tests for all new functionality, aim for comprehensive coverage

### Pull Request Process

1. **Fork & Branch**: Create feature branch from `develop`
2. **Develop**: Implement changes with tests
3. **Quality**: Ensure all CI checks pass (tests, linting, security)
4. **Review**: Submit PR with clear description and test coverage
5. **Deploy**: Automatic deployment after merge to `main`

### Testing Requirements

- **Unit Tests**: All models, views, and business logic
- **Integration Tests**: End-to-end functionality and workflows
- **Security Tests**: Authentication, authorization, and data validation
- **Performance Tests**: Database queries and page load times (where applicable)

## License

[License information to be added]

---

For detailed development guidance and architectural decisions, see [CLAUDE.md](CLAUDE.md).
