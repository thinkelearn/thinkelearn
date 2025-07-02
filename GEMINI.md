
# Gemini Project Analysis

This document provides a summary of the `thinkelearn` project based on an analysis of its codebase.

## Project Overview

`thinkelearn` is a web application built with the Django framework and the Wagtail CMS. It appears to be an e-learning platform. The project also uses Node.js and Tailwind CSS for frontend development.

## Key Technologies

- **Backend:** Django, Wagtail CMS
- **Frontend:** Tailwind CSS, vanilla JavaScript
- **Database:** PostgreSQL (in production/testing), SQLite (in development)
- **Deployment:** Docker, Railway
- **Testing:** pytest, coverage.py
- **Linting & Formatting:** ruff, mypy, pre-commit
- **CI/CD:** GitHub Actions

## Project Structure

The project is organized into several Django apps:

- `home`: Core application with pages like About, Contact, and Portfolio.
- `blog`: A blogging application.
- `communications`: Handles communication features like SMS and voicemail, likely integrating with Twilio.
- `search`: Provides search functionality.
- `thinkelearn`: The main project directory containing settings and base configuration.

## Development Workflow

### Setup

1. **Python:** The project uses Python 3.13 with dependencies managed by `uv` and defined in `pyproject.toml`.
2. **Node.js:** Node.js 20 is used for frontend asset management. Dependencies are listed in `package.json`.
3. **Installation:**
    - Python dependencies: `uv sync --group test --group dev`
    - Node.js dependencies: `npm ci`

### Building Frontend Assets

- To build CSS for development (with watching): `npm run build-css`
- To build CSS for production (minified): `npm run build-css-prod`

### Running the Application

- The application can be run using `uv run python manage.py runserver`.
- The production server uses `gunicorn`.

### Testing

- Tests are run with `pytest`. The command `uv run python manage.py test` is used in the CI pipeline.
- Test configuration is in `pyproject.toml`.
- The project aims for a minimum of 50% test coverage.

### Linting and Formatting

- `ruff` is used for linting and formatting.
- `mypy` is used for type checking.
- `pre-commit` is configured to run these checks automatically before commits.

### CI/CD

- The CI/CD pipeline is defined in `.github/workflows/ci.yml`.
- The pipeline includes jobs for:
  - Running tests against a PostgreSQL database.
  - Linting and formatting checks.
  - Security scanning with `safety` and `bandit`.
  - Building and verifying the CSS.
  - Building a Docker image for testing purposes.

## Integrations

- **Twilio:** The project integrates with Twilio for SMS and voice capabilities, as indicated by the settings in `thinkelearn/settings/base.py` and the `communications` app.
- **Sentry:** Sentry is used for error monitoring.
- **AWS S3:** `django-storages` is used, suggesting that AWS S3 is likely used for file storage in production.

## Noteworthy Files

- `pyproject.toml`: Defines project metadata, dependencies, and tool configurations.
- `package.json`: Defines Node.js dependencies and scripts.
- `.github/workflows/ci.yml`: The CI/CD pipeline configuration.
- `thinkelearn/settings/base.py`: Base Django settings, including integrations.
- `manage.py`: The Django management script.
- `Dockerfile`: Defines the production container image.
- `docker-compose.yml`: For local development environment setup.
