# THINK eLearn

A modern eLearning platform built with Django and Wagtail CMS.

![CI Status](https://github.com/thinkelearn/thinkelearn/workflows/CI%20Pipeline/badge.svg)
![Python](https://img.shields.io/badge/python-3.13-blue)
![Django](https://img.shields.io/badge/django-6.0-green)

## Overview

THINK eLearn is a production-ready educational technology platform combining Django's robust backend with Wagtail's intuitive content management system. Features include a modern Tailwind CSS design, comprehensive communications integration, and automated deployment on Railway.

## Tech Stack

- **Backend**: Django 6.0 with Wagtail 7.2.1 CMS
- **Database**: PostgreSQL (production), SQLite (development)
- **Frontend**: Tailwind CSS with custom brown/orange design system
- **Package Management**: uv for Python, npm for Node.js
- **Deployment**: Railway with automated CI/CD

## Features

- **Content Management**: Flexible page creation via Wagtail CMS
- **Learning Management System**: SCORM-compliant course delivery with progress tracking, prerequisites, and reviews
- **Payment Processing**: Complete Stripe integration with multiple pricing models (free, fixed, pay-what-you-can)
- **Accounting Ledger**: Double-entry bookkeeping system for charges, refunds, fees, and adjustments
- **Blog System**: Categories, tags, and related posts
- **Portfolio Showcase**: Project galleries with case studies and ZIP package handling
- **Contact System**: Forms with Twilio SMS/voicemail integration
- **Admin Interfaces**: Wagtail (content) and Django (system) admin with comprehensive payment tracking
- **Responsive Design**: Mobile-first Tailwind CSS with custom brown/orange theme

## Quick Start

### Option 1: Docker (Recommended)

```bash
git clone https://github.com/thinkelearn/thinkelearn
cd thinkelearn
make setup  # Complete setup with admin and pages
```

Access at <http://localhost:8000>

- **Wagtail Admin**: `/admin/` (Content management)
- **Django Admin**: `/django-admin/` (System administration)

### Option 2: Traditional Setup

```bash
git clone https://github.com/thinkelearn/thinkelearn
cd thinkelearn

# Install dependencies
uv sync

# Note: requirements.txt is generated via `uv export --all-extras --no-hashes`
# and should not be edited by hand.
npm install

# Setup database
uv run python manage.py migrate
uv run python manage.py createsuperuser

# Start servers
uv run python manage.py runserver  # Terminal 1
npm run build-css                  # Terminal 2

# Background tasks (Celery)
redis-server                       # Terminal 3
celery -A thinkelearn worker -l info  # Terminal 4
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

For detailed LMS implementation information, see [docs/lms-implementation-plan.md](docs/lms-implementation-plan.md).

## Payment System

THINK eLearn includes a production-ready payment system built on Stripe with accounting-grade financial tracking.

### Payment Features

- **Multiple Pricing Models**: Free courses, fixed-price, and pay-what-you-can (PWYC)
- **Secure Processing**: PCI DSS compliant via Stripe Checkout Session
- **Automated Refunds**: 30-day refund window (configurable per course)
- **Accounting Ledger**: Complete double-entry bookkeeping for all transactions
- **Partial Refunds**: Support for multiple partial refunds per payment
- **Email Notifications**: Automated refund confirmation emails
- **Admin Interface**: Comprehensive payment tracking with inline ledger entries

### Payment Models

- **CourseProduct**: Defines pricing for courses (free/fixed/PWYC)
- **EnrollmentRecord**: Tracks enrollment status and payment state
- **Payment**: Records payment transactions with denormalized totals
- **PaymentLedgerEntry**: Audit trail of all charges, refunds, fees, and adjustments
- **WebhookEvent**: Ensures idempotent webhook processing

### Setting Up Payments

**Environment Variables Required:**

```bash
STRIPE_SECRET_KEY=sk_test_...          # Test mode for development
STRIPE_PUBLISHABLE_KEY=pk_test_...     # Test mode for development
STRIPE_WEBHOOK_SECRET=whsec_...        # From Stripe dashboard
```

**Create Course Products:**

1. Navigate to Django Admin → Course Products → Add Course Product
2. Select course and pricing type (FREE, FIXED, PAY_WHAT_YOU_CAN)
3. Set price/amount limits if applicable
4. Configure refund window (default: 30 days)
5. Save and publish

**Test Payment Flow:**

1. Browse to `/courses/`
2. Select a paid course
3. Click "Enroll" button
4. Enter amount (if PWYC) and proceed to checkout
5. Use Stripe test card: `4242 4242 4242 4242`
6. Complete payment and verify enrollment activation

### Payment Testing

**49 comprehensive tests** covering:

- Payment model business logic and totals calculation
- Checkout session creation and Stripe integration
- Webhook processing (success, failure, refunds)
- Idempotency and race condition handling
- Refund workflows (full, partial, multiple)
- Email notifications
- Error handling and retry logic

**Run payment tests:**

```bash
# Docker
docker-compose exec web python manage.py test payments

# Local
python manage.py test payments
# or
uv run pytest payments/tests/ -v
```

### Production Status

**Phases 1-5 COMPLETE** (Ready for production preparation):

- ✅ Data models with comprehensive tests (49 tests)
- ✅ Stripe Checkout Session integration
- ✅ Webhook processing with idempotency
- ✅ Automated refund handling
- ✅ Accounting ledger system
- ✅ Admin interface with financial tracking

**Next Steps** (Phases 6-7):

- Security audit and penetration testing
- Performance optimization
- Monitoring and alerting
- Production deployment

For complete payment system documentation, see [docs/lms-implementation-plan.md](docs/lms-implementation-plan.md).

## Documentation

For detailed information, see the `/docs` directory:

- **[LMS Implementation Plan](docs/lms-implementation-plan.md)** - Complete payment and LMS implementation guide (Phases 1-5 COMPLETE)
- **[Docker Development Guide](docs/docker-development.md)** - Container setup, pgAdmin, troubleshooting
- **[Testing Guide](docs/testing-guide.md)** - Testing philosophy, commands, and best practices
- **[CI/CD Guide](docs/ci-cd-guide.md)** - Deployment pipeline and Railway configuration
- **[Stripe Frontend Integration](docs/stripe-frontend-integration.md)** - Payment UI and checkout flow
- **[Django Background Tasks](docs/django-background-tasks.md)** - Future async task implementation guide
- **[CLAUDE.md](CLAUDE.md)** - Complete project documentation and development guidance

## License

[License information to be added]
