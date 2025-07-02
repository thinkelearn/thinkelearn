from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from blog.models import BlogIndexPage
from home.models import (
    AboutPage,
    ContactFormField,
    ContactPage,
    HomePage,
    PortfolioIndexPage,
)


class CreateAdminCommandTest(TestCase):
    def setUp(self):
        self.User = get_user_model()

    def test_create_admin_command(self):
        """Test creating admin user via management command"""
        # Ensure no admin exists
        self.assertFalse(self.User.objects.filter(username="admin").exists())

        # Run command
        call_command("create_admin")

        # Verify admin was created
        admin = self.User.objects.get(username="admin")
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_staff)
        self.assertEqual(admin.email, "admin@thinkelearn.com")

    def test_create_admin_command_with_reset(self):
        """Test resetting existing admin user"""
        # Create initial admin
        self.User.objects.create_superuser(
            username="admin", email="old@example.com", password="oldpass"
        )

        # Run command with reset
        call_command("create_admin", reset=True)

        # Verify admin was recreated with new settings
        admin = self.User.objects.get(username="admin")
        self.assertEqual(admin.email, "admin@thinkelearn.com")

    def test_create_admin_without_reset_existing(self):
        """Test command when admin already exists without reset"""
        # Create initial admin
        existing_admin = self.User.objects.create_superuser(
            username="admin", email="existing@example.com", password="existingpass"
        )

        # Run command without reset (should not change existing)
        call_command("create_admin")

        # Verify admin unchanged
        admin = self.User.objects.get(username="admin")
        self.assertEqual(admin.email, "existing@example.com")
        self.assertEqual(admin.id, existing_admin.id)


class SetupPagesCommandTest(WagtailPageTestCase):
    def setUp(self):
        # Create a root page and homepage for testing
        self.root_page = Page.get_first_root_node()
        self.homepage = HomePage(
            title="THINK eLearn", slug="home", hero_title="Test Home"
        )
        self.root_page.add_child(instance=self.homepage)
        self.homepage.save_revision().publish()

    def test_setup_pages_command(self):
        """Test setting up all core pages via management command"""
        # Verify no pages exist initially (except homepage)
        self.assertFalse(AboutPage.objects.exists())
        self.assertFalse(ContactPage.objects.exists())
        self.assertFalse(BlogIndexPage.objects.exists())
        self.assertFalse(PortfolioIndexPage.objects.exists())

        # Run setup command
        call_command("setup_pages")

        # Verify pages were created
        self.assertTrue(AboutPage.objects.exists())
        self.assertTrue(ContactPage.objects.exists())
        self.assertTrue(BlogIndexPage.objects.exists())
        self.assertTrue(PortfolioIndexPage.objects.exists())

        # Verify page details
        about_page = AboutPage.objects.first()
        self.assertEqual(about_page.title, "About Us")
        self.assertEqual(about_page.slug, "about")
        self.assertEqual(about_page.hero_title, "About THINK eLearn")

        contact_page = ContactPage.objects.first()
        self.assertEqual(contact_page.title, "Contact")
        self.assertEqual(contact_page.phone, "+1 (289) 816-3749")
        self.assertEqual(contact_page.email, "info@thinkelearn.com")

        blog_page = BlogIndexPage.objects.first()
        self.assertEqual(blog_page.title, "Blog")
        self.assertEqual(blog_page.slug, "blog")

        portfolio_page = PortfolioIndexPage.objects.first()
        self.assertEqual(portfolio_page.title, "Portfolio")
        self.assertEqual(portfolio_page.slug, "portfolio")

    def test_setup_pages_contact_form_fields(self):
        """Test that contact form fields are created correctly"""
        # Run setup command
        call_command("setup_pages")

        contact_page = ContactPage.objects.first()
        form_fields = ContactFormField.objects.filter(page=contact_page).order_by(
            "sort_order"
        )

        # Verify all form fields were created
        self.assertEqual(form_fields.count(), 4)

        # Verify field details
        name_field = form_fields[0]
        self.assertEqual(name_field.label, "Name")
        self.assertEqual(name_field.field_type, "singleline")
        self.assertTrue(name_field.required)

        email_field = form_fields[1]
        self.assertEqual(email_field.label, "Email")
        self.assertEqual(email_field.field_type, "email")
        self.assertTrue(email_field.required)

        subject_field = form_fields[2]
        self.assertEqual(subject_field.label, "Subject")
        self.assertEqual(subject_field.field_type, "singleline")
        self.assertTrue(subject_field.required)

        message_field = form_fields[3]
        self.assertEqual(message_field.label, "Message")
        self.assertEqual(message_field.field_type, "multiline")
        self.assertTrue(message_field.required)

    def test_setup_pages_idempotent(self):
        """Test that running setup_pages multiple times doesn't create duplicates"""
        # Run setup command twice
        call_command("setup_pages")
        call_command("setup_pages")

        # Verify only one of each page type exists
        self.assertEqual(AboutPage.objects.count(), 1)
        self.assertEqual(ContactPage.objects.count(), 1)
        self.assertEqual(BlogIndexPage.objects.count(), 1)
        self.assertEqual(PortfolioIndexPage.objects.count(), 1)

    def test_setup_pages_without_homepage(self):
        """Test setup_pages command when no homepage exists"""
        # Remove the homepage
        self.homepage.delete()

        # Run setup command (should handle gracefully)
        call_command("setup_pages")

        # Should not create pages without a homepage
        self.assertFalse(AboutPage.objects.exists())

    def test_setup_pages_page_hierarchy(self):
        """Test that pages are created as children of homepage"""
        call_command("setup_pages")

        # Verify all pages are children of homepage
        about_page = AboutPage.objects.first()
        contact_page = ContactPage.objects.first()
        blog_page = BlogIndexPage.objects.first()
        portfolio_page = PortfolioIndexPage.objects.first()

        self.assertEqual(about_page.get_parent(), self.homepage)
        self.assertEqual(contact_page.get_parent(), self.homepage)
        self.assertEqual(blog_page.get_parent(), self.homepage)
        self.assertEqual(portfolio_page.get_parent(), self.homepage)

    def test_setup_pages_published_status(self):
        """Test that created pages are published"""
        call_command("setup_pages")

        about_page = AboutPage.objects.first()
        contact_page = ContactPage.objects.first()
        blog_page = BlogIndexPage.objects.first()
        portfolio_page = PortfolioIndexPage.objects.first()

        self.assertTrue(about_page.live)
        self.assertTrue(contact_page.live)
        self.assertTrue(blog_page.live)
        self.assertTrue(portfolio_page.live)


class ManagementCommandsIntegrationTest(WagtailPageTestCase):
    """Test full setup workflow using both commands"""

    def test_complete_setup_workflow(self):
        """Test the complete setup workflow used in production"""
        User = get_user_model()

        # Step 1: Create admin user
        call_command("create_admin")
        admin = User.objects.get(username="admin")
        self.assertTrue(admin.is_superuser)

        # Step 2: Set up initial page structure
        # First create homepage (simulating what happens in production)
        root_page = Page.get_first_root_node()
        homepage = HomePage(title="THINK eLearn", slug="home")
        root_page.add_child(instance=homepage)
        homepage.save_revision().publish()

        # Step 3: Set up all other pages
        call_command("setup_pages")

        # Verify complete site structure
        self.assertTrue(HomePage.objects.exists())
        self.assertTrue(AboutPage.objects.exists())
        self.assertTrue(ContactPage.objects.exists())
        self.assertTrue(BlogIndexPage.objects.exists())
        self.assertTrue(PortfolioIndexPage.objects.exists())

        # Verify admin can access all pages
        self.assertTrue(admin.has_perm("wagtailadmin.access_admin"))

        # Verify contact form is functional
        contact_page = ContactPage.objects.first()
        form_fields = ContactFormField.objects.filter(page=contact_page)
        self.assertEqual(form_fields.count(), 4)
