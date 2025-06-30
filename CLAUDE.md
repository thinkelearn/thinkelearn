# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

THINK eLearn is a Django-based eLearning platform website built with Wagtail CMS, designed to be hosted at thinkelearn.com using Railway. The project uses modern Python tooling with `uv` for dependency management and Tailwind CSS for styling.

## Architecture

- **Framework**: Django 5.2.3 with Wagtail 7.0.1 CMS
- **Database**: SQLite for development, PostgreSQL for production (Railway)
- **Styling**: Tailwind CSS with custom design system
- **Deployment**: Railway with Docker containerization
- **Apps**:
  - `home`: HomePage model with rich content fields for landing page
  - `search`: Built-in Wagtail search functionality
  - Additional apps planned: blog, portfolio, contact, services

## Settings Structure

Split settings configuration:

- `thinkelearn/settings/base.py`: Base configuration shared across environments
- `thinkelearn/settings/dev.py`: Development settings (DEBUG=True, console email backend)
- `thinkelearn/settings/production.py`: Production settings (DEBUG=False)
- Default: Development settings loaded by `manage.py`

## Key Commands

### Development

```bash
# Start development server
python manage.py runserver

# Database management
python manage.py migrate
python manage.py makemigrations
python manage.py createsuperuser

# Static files
python manage.py collectstatic

# Install/update dependencies
uv sync
uv add <package-name>

# CSS build (Tailwind)
npm run build-css          # Development with watch mode
npm run build-css-prod     # Production build with minification
```

### Production/Docker

```bash
# Build Docker image
docker build -t thinkelearn .

# Run with Docker
docker run -p 8000:8000 thinkelearn

# Railway deployment
# Uses Railway's automatic deployment from git
```

## Dependencies

The project uses `uv` for dependency management:

- Core dependencies in `pyproject.toml`
- Full dependency tree locked in `uv.lock`
- Requirements exported to `requirements.txt` for Docker

Key dependencies:

- **Django/Wagtail**: CMS and web framework
- **psycopg**: PostgreSQL database adapter for production
- **gunicorn**: WSGI HTTP server for production
- **whitenoise**: Static file serving
- **Tailwind CSS**: Utility-first CSS framework (via npm)

## Site Structure

### Planned Page Types

- **HomePage**: Landing page with hero, features, testimonials
- **AboutPage**: Company story, team, mission/values
- **BlogIndexPage & BlogPage**: Content marketing and articles
- **PortfolioIndexPage & ProjectPage**: Showcase work and case studies
- **ContactPage**: Contact form, locations, social links
- **ServicePage**: Future service offerings

### URL Structure

- `/admin/`: Wagtail admin interface
- `/django-admin/`: Django admin interface
- `/search/`: Search functionality
- `/documents/`: Document serving
- `/blog/`: Blog section
- `/portfolio/`: Project showcase
- `/contact/`: Contact page
- All other URLs handled by Wagtail's page serving

## Styling & Frontend

### Tailwind CSS Setup

- Source CSS: `thinkelearn/static/css/src/input.css`
- Built CSS: `thinkelearn/static/css/thinkelearn.css`
- Config: `tailwind.config.js` with custom brand colors and typography
- Build process: npm scripts for development and production

### Design System

- **Primary colors**: Warm brown theme (#361612 to #784421 variants) - Professional, educational feel
- **Secondary colors**: Orange accent theme (#ff6600 variants) - Brand highlight color matching logo
- **Neutral colors**: Warm gray theme (#1c1917 to #fafaf9 variants) - Better harmony with brown palette
- **Typography**: Inter (body), Poppins (headings)
- **Components**: Buttons, cards, forms with consistent styling using warm color palette
- **Responsive**: Mobile-first approach with Tailwind breakpoints

#### Color Usage Guidelines

- **Headers/Navigation**: `text-primary-800` or `bg-primary-800` (dark brown)
- **Buttons/CTAs**: `bg-secondary-500 hover:bg-secondary-600` (orange)
- **Links**: `text-secondary-500 hover:text-secondary-600` (orange)
- **Body text**: `text-neutral-700` (warm dark gray)
- **Light backgrounds**: `bg-neutral-50` (warm off-white)
- **Section backgrounds**: `bg-primary-50` (very light brown tint)
- **Borders**: `border-neutral-200` or `border-primary-200` (warm grays)

## Development Workflow

1. **Backend changes**: Edit Django/Wagtail code, run migrations if needed
2. **Frontend changes**: Edit templates and CSS, Tailwind auto-rebuilds
3. **Testing**: Use Django's built-in test framework
4. **Production**: Build CSS with `npm run build-css-prod` before deployment

## Important Files

- **Documentation**: `/docs/` directory contains detailed planning documents
  - `site-plan.md`: Overall project plan and content strategy
  - `wagtail-models.md`: Detailed page model specifications
  - `tailwind-setup.md`: Complete Tailwind integration guide
- **Templates**: Follow Wagtail conventions in app-specific template directories
- **Static files**: App-specific in `<app>/static/`, project-wide in `thinkelearn/static/`

## Production Considerations

- **Security**: DEBUG=False, proper SECRET_KEY, ALLOWED_HOSTS configuration
- **Database**: PostgreSQL via Railway's managed database
- **Static files**: Collected and served via whitenoise
- **Performance**: CSS minification, image optimization, caching strategies
- **SEO**: Wagtail's built-in SEO fields, structured data, meta tags

## Next Development Steps

1. Implement enhanced HomePage model with StreamFields
2. Set up Tailwind CSS build process
3. Create base templates with responsive design
4. Develop blog and portfolio functionality
5. Add contact form with email handling
6. Configure Railway deployment pipeline
