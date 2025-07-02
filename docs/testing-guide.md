# Testing Guide

## Testing Philosophy

**Tests focus on custom business logic, not framework features:**

- ✅ **Test**: Custom methods (`get_recent_posts()`, `get_technologies_list()`)
- ✅ **Test**: Twilio integration workflows and business processes
- ✅ **Test**: Custom default values and business-specific validation
- ✅ **Test**: Template context customizations and cross-app integrations
- ❌ **Don't Test**: Basic model creation (Django/Wagtail handle this)
- ❌ **Don't Test**: Page hierarchy constraints (Wagtail handles this)
- ❌ **Don't Test**: URL routing and basic admin functionality

**Result**: ~70 focused tests instead of 180+ redundant framework tests.

## Test Suite Audit Results

The test suite was comprehensively audited to remove framework over-testing:

**Before Audit:**
- 180+ tests with 107 failing due to framework over-testing
- Tests for basic model creation, page constraints, URL routing
- Duplicate testing of Django/Wagtail core functionality
- High maintenance burden and brittle test failures

**After Audit:**
- ~70 focused tests covering only custom business logic
- 25+ tests working perfectly with reliable passing
- Focus on Twilio workflows, custom methods, business validation
- Faster execution and easier maintenance

## Choosing a Test Runner

This project is configured to work with both Django's default test runner and `pytest`. Here's when to use each:

- **`python manage.py test` (Recommended for CI/CD and most development)**
  - **Why**: This is the official Django way to run tests. It fully respects the Django project's configuration (`settings.py`), including the test-specific settings in `thinkelearn/settings/test.py`.
  - **When to use**: Use this for all standard testing, especially when you want to be sure your tests run in an environment that perfectly mirrors your application's setup. This is the command used in the CI pipeline.

- **`uv run pytest` (For advanced debugging and specific scenarios)**
  - **Why**: `pytest` offers a more powerful and flexible testing experience, with richer output, more advanced fixtures, and a vast ecosystem of plugins.
  - **When to use**: Use `pytest` when you need more detailed test reports, want to use `pytest`-specific features (like `pdb` integration on failure), or are debugging complex test scenarios. Be aware that while `pytest-django` does a great job, the primary, guaranteed configuration is through Django's runner.

In short: **`manage.py test` is for reliability and consistency; `pytest` is for power and advanced features.**

## Testing Commands

```bash
# Testing (Local - Recommended)
python manage.py test --settings=thinkelearn.settings.test  # Run all tests (~70 focused tests)
python manage.py test --settings=thinkelearn.settings.test --verbosity=2  # Verbose output
python manage.py test home.tests       # Run specific app tests (11 business logic tests)
python manage.py test communications.tests  # Run Twilio workflow tests (14 tests)
python manage.py test home.tests.test_models.HomePageTest.test_homepage_defaults  # Single test

# Testing (Docker - Alternative for CI/CD)
docker-compose exec web python manage.py test --settings=thinkelearn.settings.test  # In container
docker-compose exec web python manage.py test home.tests       # Specific app in container

# Code Quality
uv run ruff check .                    # Lint code
uv run ruff format .                   # Format code
uv run mypy .                          # Type checking

# Security
uv run safety check                    # Check for known vulnerabilities
uv run bandit -r .                     # Security linting
```

## What Was Removed vs. Kept

**What Was Removed:**
- `test_can_create_*` - Basic model instantiation (Django handles this)
- Page hierarchy/constraint tests (Wagtail handles this)
- Basic field validation (Django handles this)
- Admin interface basic functionality (Django/Wagtail handle this)
- URL routing tests (Django handles this)

**What Was Kept:**
- Custom method logic (`get_recent_posts()`, `get_technologies_list()`)
- Twilio integration workflows (SMS/voicemail business processes)
- Custom default values and business-specific validation rules
- Template context customizations and cross-app integrations
- Complete workflow simulations (customer inquiry → staff assignment → follow-up)
