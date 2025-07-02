import os

import django
import pytest
from django.conf import settings


def pytest_configure(config):
    """Configure Django settings for pytest"""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "thinkelearn.settings.test")
    django.setup()


@pytest.fixture(scope="session")
def django_db_setup():
    """Setup test database"""
    settings.DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }


@pytest.fixture
def wagtail_root_page():
    """Create a root page for Wagtail tests"""
    from wagtail.models import Page, Site

    from home.models import HomePage

    # Create root page if it doesn't exist
    root = Page.objects.filter(depth=1).first()
    if not root:
        root = Page.add_root(title="Root")

    # Create homepage if it doesn't exist
    try:
        homepage = HomePage.objects.first()
        if not homepage:
            homepage = HomePage(
                title="THINK eLearn", slug="home", hero_title="Test Home Page"
            )
            root.add_child(instance=homepage)
            homepage.save_revision().publish()

            # Create site if it doesn't exist
            if not Site.objects.exists():
                Site.objects.create(
                    hostname="localhost",
                    port=8000,
                    root_page=homepage,
                    is_default_site=True,
                )
    except Exception:
        # Fallback: just return root page
        homepage = root

    return homepage


@pytest.fixture
def admin_user(django_user_model):
    """Create an admin user for testing"""
    return django_user_model.objects.create_user(
        username="admin",
        email="admin@example.com",
        password="testpass123",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def staff_user(django_user_model):
    """Create a staff user for testing"""
    return django_user_model.objects.create_user(
        username="staff",
        email="staff@example.com",
        password="testpass123",
        is_staff=True,
    )


@pytest.fixture
def regular_user(django_user_model):
    """Create a regular user for testing"""
    return django_user_model.objects.create_user(
        username="user", email="user@example.com", password="testpass123"
    )
