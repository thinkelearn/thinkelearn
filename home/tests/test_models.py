from django.test import TestCase
from wagtail.models import Page

from home.models import (
    AboutPage,
    ContactPage,
    HomePage,
)

# BUSINESS LOGIC TESTS ONLY
# Tests focus on custom methods, defaults, and business-specific functionality


class HomePageTest(TestCase):
    def setUp(self):
        self.root_page = Page.add_root(title="Root")

    def test_homepage_defaults(self):
        """Test custom default values for business requirements"""
        homepage = HomePage(title="Test")
        self.assertEqual(homepage.hero_title, "Empowering Learning Through Innovation")
        self.assertEqual(homepage.hero_cta_text, "Get Started")
        self.assertEqual(homepage.features_title, "Why Choose THINK eLearn")

    def test_get_recent_posts_with_no_blog(self):
        """Test custom method when no blog exists"""
        homepage = HomePage(title="Test Home Page", slug="home")
        self.root_page.add_child(instance=homepage)
        recent_posts = homepage.get_recent_posts()
        self.assertEqual(len(recent_posts), 0)

    def test_get_recent_posts_disabled(self):
        """Test custom method when feature is disabled"""
        homepage = HomePage(
            title="Test Home Page", slug="home", show_recent_posts=False
        )
        self.root_page.add_child(instance=homepage)
        recent_posts = homepage.get_recent_posts()
        self.assertEqual(len(recent_posts), 0)


class AboutPageTest(TestCase):
    def test_about_page_defaults(self):
        """Test custom default values for business requirements"""
        about_page = AboutPage(title="About")
        self.assertEqual(about_page.hero_title, "About THINK eLearn")
        self.assertEqual(about_page.story_title, "Our Story")
        self.assertEqual(about_page.mission_title, "Our Mission")


class ContactPageTest(TestCase):
    def test_contact_page_defaults(self):
        """Test custom default values for business requirements"""
        contact_page = ContactPage(title="Contact")
        self.assertEqual(contact_page.hero_title, "Contact Us")
        self.assertTrue(contact_page.show_contact_info)
        self.assertTrue(contact_page.show_faq)
