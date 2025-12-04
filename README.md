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
- **Learning Management System**: SCORM-compliant course delivery with progress tracking
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

- **Wagtail Admin** (`/admin/`): Content management, pages, media, courses
- **Django Admin** (`/django-admin/`): User management, communications, SCORM packages, system settings

## Learning Management System (LMS)

THINK eLearn includes a comprehensive LMS built on wagtail-lms with extensive custom enhancements.

### LMS Features

- **SCORM Support**: Full SCORM 1.2 and 2004 compliance
- **Course Catalog**: Searchable course library with categories and tags
- **Prerequisites**: Course dependency management
- **Progress Tracking**: Student dashboard with completion statistics
- **Reviews & Ratings**: 5-star rating system with moderation
- **Instructors**: Course instructor profiles with photos and bios
- **Enrollment Management**: Enrollment limits and validation
- **Responsive Player**: Full-screen SCORM player with auto-save

### Setting Up the LMS

After initial project setup, run the LMS setup command:

```bash
# Docker
docker-compose run --rm web python manage.py setup_lms --with-categories --with-tags

# Traditional
python manage.py setup_lms --with-categories --with-tags
```

This creates:
- Courses index page at `/courses/`
- Learner dashboard at `/dashboard/`
- Default categories (Programming, Web Development, Data Science, Design, Business, Cybersecurity)
- Default tags (Python, JavaScript, React, Machine Learning, etc.)

### Creating Courses

**1. Upload SCORM Package:**
- Navigate to Django Admin → SCORM Packages → Add SCORM Package
- Upload your .zip SCORM package
- The system automatically extracts and parses the package

**2. Create Course Page:**
- Go to Wagtail Admin → Pages → Courses
- Click "Add child page" → Choose "Course"
- Fill in course details:
  - Title, description, and learning objectives
  - Select SCORM package
  - Choose categories and tags
  - Set difficulty level and duration
  - Add prerequisites (if any)
  - Set enrollment limit (optional)
  - Add instructors
- Publish the course

**3. Students Can:**
- Browse courses at `/courses/`
- Filter by category, tag, or search
- Enroll in courses
- Track progress at `/dashboard/`
- Rate and review completed courses

### LMS Management

**Course Categories & Tags:**
- Manage via Wagtail Admin → Snippets
- Use Font Awesome icons for categories (e.g., `fa-code`, `fa-database`)

**Course Reviews:**
- Moderate via Django Admin → Course Reviews
- Approve/reject student reviews
- Monitor ratings and feedback

**Student Progress:**
- View enrollment data in Django Admin → Course Enrollments
- Track SCORM attempts and scores
- Monitor completion rates

### LMS URLs

- `/courses/` - Course catalog
- `/courses/{slug}/` - Individual course pages
- `/dashboard/` - Student dashboard (requires login)
- `/lms/course/{id}/play/` - SCORM player

For detailed LMS implementation information, see [docs/lms-implementation-status.md](docs/lms-implementation-status.md).

## Documentation

For detailed information, see the `/docs` directory:

- **[LMS Implementation Guide](docs/lms-implementation-status.md)** - Complete LMS setup, features, and development status
- **[Docker Development Guide](docs/docker-development.md)** - Container setup, pgAdmin, troubleshooting
- **[Testing Guide](docs/testing-guide.md)** - Testing philosophy, commands, and best practices
- **[CI/CD Guide](docs/ci-cd-guide.md)** - Deployment pipeline and Railway configuration
- **[CLAUDE.md](CLAUDE.md)** - Complete project documentation and development guidance

## License

[License information to be added]
