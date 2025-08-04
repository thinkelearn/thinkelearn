# CI/CD Guide

## CI/CD Pipeline Overview

### Continuous Integration (GitHub Actions)

The project uses **GitHub Actions** for automated testing and quality assurance:

- **Streamlined Testing**: 25 focused business logic tests (no framework over-testing)
- **Code Quality**: Linting, formatting, and type checking
- **Security Scanning**: Vulnerability and security analysis
- **Build Verification**: CSS compilation and static file generation
- **Production Environment**: Tests run against PostgreSQL

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

## CI/CD Development Setup

```bash
# Quick setup for CI/CD development
./scripts/setup-ci-cd.sh              # Automated CI/CD environment setup
```

## Manual Deployment Steps

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

## Environment Variables

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
