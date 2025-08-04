# THINK eLearn

A modern eLearning platform built with Django and Wagtail CMS.

![CI Status](https://github.com/think-elearn/thinkelearn/workflows/CI%20Pipeline/badge.svg)
![Python](https://img.shields.io/badge/python-3.13-blue)
![Django](https://img.shields.io/badge/django-5.2.3-green)

## Overview

THINK eLearn is a production-ready educational technology platform combining Django's robust backend with Wagtail's intuitive content management system. Features include a modern Tailwind CSS design, comprehensive communications integration, and automated deployment on Railway.

## Tech Stack

- **Backend**: Django 5.2.3 with Wagtail 7.0.1 CMS
- **Database**: PostgreSQL (production), SQLite (development)
- **Frontend**: Tailwind CSS with custom brown/orange design system
- **Package Management**: uv for Python, npm for Node.js
- **Deployment**: Railway with automated CI/CD

## Features

- **Content Management**: Flexible page creation via Wagtail CMS
- **Blog System**: Categories, tags, and related posts
- **Portfolio Showcase**: Project galleries with case studies
- **Contact System**: Forms with Twilio SMS/voicemail integration
- **Admin Interfaces**: Wagtail (content) and Django (system) admin
- **Responsive Design**: Mobile-first Tailwind CSS with custom theme

## Quick Start

### Option 1: Docker (Recommended)

```bash
git clone https://github.com/think-elearn/thinkelearn
cd thinkelearn
make setup  # Complete setup with admin and pages
```

Access at <http://localhost:8000>

- **Wagtail Admin**: `/admin/` (Content management)
- **Django Admin**: `/django-admin/` (System administration)

### Option 2: Traditional Setup

```bash
git clone https://github.com/think-elearn/thinkelearn
cd thinkelearn

# Install dependencies
uv sync
npm install

# Setup database
uv run python manage.py migrate
uv run python manage.py createsuperuser

# Start servers
uv run python manage.py runserver  # Terminal 1
npm run build-css                  # Terminal 2
```

## Prerequisites

**Docker Option:**

- Docker and Docker Compose
- Git

**Traditional Option:**

- Python 3.13+ with [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- Git

## Development Commands

### Docker Development

```bash
# Quick start
make            # Start development environment (default)
make start      # Start all containers
make setup      # Full setup with admin user and sample pages

# Container management
make stop       # Stop all containers
make status     # Show container status
make logs       # Show logs from all containers

# Cleanup and maintenance
make reset      # Clean up Docker resources (preserves database)
make clean      # Full cleanup (⚠️  REMOVES DATABASE)
make rebuild    # Rebuild containers from scratch

# Alternative: Direct script usage
./start.sh start    # Same commands available via script
./start.sh --help   # Show all available options
```

### Traditional Development

```bash
# Django management
python manage.py runserver       # Start development server
python manage.py migrate         # Run migrations
python manage.py createsuperuser # Create admin user

# CSS compilation
npm run build-css               # Development with watch mode
npm run build-css-prod          # Production build

# Testing
python manage.py test           # Run test suite
uv run ruff check .            # Code linting
```

## Admin Interfaces

- **Wagtail Admin** (`/admin/`): Content management, pages, media
- **Django Admin** (`/django-admin/`): User management, communications, system settings

## Documentation

For detailed information, see the `/docs` directory:

- **[Docker Development Guide](docs/docker-development.md)** - Container setup, pgAdmin, troubleshooting
- **[Testing Guide](docs/testing-guide.md)** - Testing philosophy, commands, and best practices
- **[CI/CD Guide](docs/ci-cd-guide.md)** - Deployment pipeline and Railway configuration
- **[CLAUDE.md](CLAUDE.md)** - Complete project documentation and development guidance

## License

[License information to be added]
