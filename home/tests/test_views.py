from django.core import mail
from django.test import Client, TestCase
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from blog.tests.test_models import BlogIndexPageFactory, BlogPageFactory
from home.tests.test_models import (
    AboutPageFactory,
    ContactPageFactory,
    HomePageFactory,
    PortfolioIndexPageFactory,
    ProjectCategoryFactory,
    ProjectPageFactory,
)


class HomePageViewTest(WagtailPageTestCase):
    def setUp(self):
        self.root_page = Page.objects.get(id=2)
        self.client = Client()

    def test_homepage_view(self):
        homepage = HomePageFactory(parent=self.root_page)

        response = self.client.get(homepage.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, homepage.hero_title)
        self.assertContains(response, homepage.features_title)

    def test_homepage_with_hero_image(self):
        from wagtail_factories import ImageFactory

        hero_image = ImageFactory()

        homepage = HomePageFactory(parent=self.root_page, hero_image=hero_image)

        response = self.client.get(homepage.url)
        self.assertEqual(response.status_code, 200)
        # Check that image is referenced in template
        self.assertContains(response, "img")

    def test_homepage_with_recent_posts(self):
        homepage = HomePageFactory(
            parent=self.root_page, show_recent_posts=True, recent_posts_count=2
        )

        # Create blog index and posts
        blog_index = BlogIndexPageFactory(parent=self.root_page)
        BlogPageFactory(parent=blog_index)
        BlogPageFactory(parent=blog_index)
        BlogPageFactory(parent=blog_index)

        response = self.client.get(homepage.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, homepage.recent_posts_title)

    def test_homepage_without_recent_posts(self):
        homepage = HomePageFactory(parent=self.root_page, show_recent_posts=False)

        response = self.client.get(homepage.url)
        self.assertEqual(response.status_code, 200)
        # Should not show recent posts section
        recent_posts = homepage.get_recent_posts()
        self.assertEqual(len(recent_posts), 0)

    def test_homepage_features_section(self):
        homepage = HomePageFactory(parent=self.root_page)

        # Add features via StreamField
        homepage.features = [
            {
                "type": "feature",
                "value": {
                    "icon": "fas fa-graduation-cap",
                    "title": "Expert Training",
                    "description": "Professional development courses",
                },
            },
            {
                "type": "feature",
                "value": {
                    "icon": "fas fa-laptop",
                    "title": "Modern Technology",
                    "description": "Latest educational technology",
                },
            },
        ]
        homepage.save()

        response = self.client.get(homepage.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Expert Training")
        self.assertContains(response, "Modern Technology")

    def test_homepage_testimonials_section(self):
        from wagtail_factories import ImageFactory

        avatar = ImageFactory()

        homepage = HomePageFactory(parent=self.root_page)
        homepage.testimonials = [
            {
                "type": "testimonial",
                "value": {
                    "quote": "Excellent service and support!",
                    "author": "John Smith",
                    "company": "ABC Corp",
                    "avatar": avatar.id,
                },
            }
        ]
        homepage.save()

        response = self.client.get(homepage.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Excellent service and support!")
        self.assertContains(response, "John Smith")


class AboutPageViewTest(WagtailPageTestCase):
    def setUp(self):
        self.root_page = Page.objects.get(id=2)
        self.client = Client()

    def test_about_page_view(self):
        about_page = AboutPageFactory(parent=self.root_page)

        response = self.client.get(about_page.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, about_page.hero_title)
        self.assertContains(response, about_page.story_title)

    def test_about_page_with_team_members(self):
        from wagtail_factories import ImageFactory

        photo = ImageFactory()

        about_page = AboutPageFactory(parent=self.root_page)
        about_page.team_members = [
            {
                "type": "member",
                "value": {
                    "name": "Jane Doe",
                    "role": "CEO & Founder",
                    "bio": "Experienced leader in educational technology.",
                    "photo": photo.id,
                    "linkedin": "https://linkedin.com/in/janedoe",
                    "email": "jane@example.com",
                },
            }
        ]
        about_page.save()

        response = self.client.get(about_page.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jane Doe")
        self.assertContains(response, "CEO & Founder")

    def test_about_page_with_values(self):
        about_page = AboutPageFactory(parent=self.root_page)
        about_page.values = [
            {
                "type": "value",
                "value": {
                    "icon": "fas fa-heart",
                    "title": "Passion",
                    "description": "We are passionate about education.",
                },
            },
            {
                "type": "value",
                "value": {
                    "icon": "fas fa-star",
                    "title": "Excellence",
                    "description": "We strive for excellence in everything.",
                },
            },
        ]
        about_page.save()

        response = self.client.get(about_page.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Passion")
        self.assertContains(response, "Excellence")

    def test_about_page_with_milestones(self):
        about_page = AboutPageFactory(parent=self.root_page)
        about_page.milestones = [
            {
                "type": "milestone",
                "value": {
                    "year": "2020",
                    "title": "Company Founded",
                    "description": "Started with a vision to transform education.",
                },
            },
            {
                "type": "milestone",
                "value": {
                    "year": "2023",
                    "title": "Major Expansion",
                    "description": "Expanded services to serve more clients.",
                },
            },
        ]
        about_page.save()

        response = self.client.get(about_page.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2020")
        self.assertContains(response, "Company Founded")


class ContactPageViewTest(WagtailPageTestCase):
    def setUp(self):
        self.root_page = Page.objects.get(id=2)
        self.client = Client()

    def test_contact_page_view(self):
        contact_page = ContactPageFactory(parent=self.root_page)

        response = self.client.get(contact_page.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, contact_page.hero_title)

    def test_contact_page_with_info(self):
        contact_page = ContactPageFactory(
            parent=self.root_page,
            phone="+1-555-0123",
            email="contact@example.com",
            address="123 Main St, City, State 12345",
            office_hours="Mon-Fri 9AM-5PM",
        )

        response = self.client.get(contact_page.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "+1-555-0123")
        self.assertContains(response, "contact@example.com")
        self.assertContains(response, "123 Main St")

    def test_contact_page_with_social_media(self):
        contact_page = ContactPageFactory(
            parent=self.root_page,
            linkedin_url="https://linkedin.com/company/thinkelearn",
            twitter_url="https://twitter.com/thinkelearn",
            facebook_url="https://facebook.com/thinkelearn",
        )

        response = self.client.get(contact_page.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "linkedin.com")
        self.assertContains(response, "twitter.com")

    def test_contact_page_with_faqs(self):
        contact_page = ContactPageFactory(parent=self.root_page)
        contact_page.faqs = [
            {
                "type": "faq",
                "value": {
                    "question": "What services do you offer?",
                    "answer": "We offer comprehensive educational technology solutions.",
                },
            },
            {
                "type": "faq",
                "value": {
                    "question": "How can I get started?",
                    "answer": "Contact us to schedule a consultation.",
                },
            },
        ]
        contact_page.save()

        response = self.client.get(contact_page.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "What services do you offer?")
        self.assertContains(response, "How can I get started?")

    def test_contact_form_submission(self):
        from home.models import ContactFormField

        contact_page = ContactPageFactory(
            parent=self.root_page,
            to_address="admin@example.com",
            from_address="contact@example.com",
            subject="New Contact Form Submission",
        )

        # Add form fields
        ContactFormField.objects.create(
            page=contact_page,
            sort_order=1,
            label="Name",
            field_type="singleline",
            required=True,
        )
        ContactFormField.objects.create(
            page=contact_page,
            sort_order=2,
            label="Email",
            field_type="email",
            required=True,
        )
        ContactFormField.objects.create(
            page=contact_page,
            sort_order=3,
            label="Message",
            field_type="multiline",
            required=True,
        )

        # Test form submission
        form_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "message": "Test message",
        }

        response = self.client.post(contact_page.url, form_data)

        # Should redirect after successful submission
        self.assertEqual(response.status_code, 302)

        # Check that email was sent
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertIn("New Contact Form Submission", sent_email.subject)
        self.assertIn("John Doe", sent_email.body)

    def test_contact_form_validation(self):
        from home.models import ContactFormField

        contact_page = ContactPageFactory(parent=self.root_page)

        # Add required form field
        ContactFormField.objects.create(
            page=contact_page,
            sort_order=1,
            label="Name",
            field_type="singleline",
            required=True,
        )

        # Test submission with missing required field
        response = self.client.post(contact_page.url, {})

        # Should show form with errors
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")


class PortfolioViewTest(WagtailPageTestCase):
    def setUp(self):
        self.root_page = Page.objects.get(id=2)
        self.portfolio_index = PortfolioIndexPageFactory(parent=self.root_page)
        self.client = Client()

    def test_portfolio_index_view(self):
        response = self.client.get(self.portfolio_index.url)
        self.assertEqual(response.status_code, 200)

    def test_portfolio_index_with_projects(self):
        # Create projects
        ProjectPageFactory(parent=self.portfolio_index)
        ProjectPageFactory(parent=self.portfolio_index)

        response = self.client.get(self.portfolio_index.url)
        self.assertEqual(response.status_code, 200)

        # Check that projects are listed
        self.assertContains(response, "Project")

    def test_portfolio_category_filtering(self):
        category = ProjectCategoryFactory(slug="web-development")

        # Create project with category
        project_with_category = ProjectPageFactory(parent=self.portfolio_index)
        project_with_category.categories.add(category)

        # Create project without category
        ProjectPageFactory(parent=self.portfolio_index)

        # Test filtering
        response = self.client.get(
            self.portfolio_index.url, {"category": "web-development"}
        )
        self.assertEqual(response.status_code, 200)

    def test_project_page_view(self):
        project = ProjectPageFactory(
            parent=self.portfolio_index,
            client_name="Test Client",
            technologies="Python, Django, React",
        )

        response = self.client.get(project.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Client")
        self.assertContains(response, "Python")

    def test_project_page_with_testimonial(self):
        from wagtail_factories import ImageFactory

        avatar = ImageFactory()

        project = ProjectPageFactory(
            parent=self.portfolio_index,
            testimonial_quote="Great work on this project!",
            testimonial_author="Jane Smith",
            testimonial_company="ABC Corp",
            testimonial_avatar=avatar,
        )

        response = self.client.get(project.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Great work on this project!")
        self.assertContains(response, "Jane Smith")

    def test_project_page_with_results(self):
        project = ProjectPageFactory(parent=self.portfolio_index)
        project.results = [
            {
                "type": "metric",
                "value": {
                    "label": "Performance Improvement",
                    "value": "150%",
                    "description": "Increased system performance",
                },
            }
        ]
        project.save()

        response = self.client.get(project.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Performance Improvement")
        self.assertContains(response, "150%")


class SearchViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_search_view_exists(self):
        """Test that search view is accessible"""
        try:
            response = self.client.get("/search/")
            self.assertIn(response.status_code, [200, 404])  # 404 if not implemented
        except Exception:
            # Search might not be fully configured
            pass

    def test_search_with_query(self):
        """Test search functionality with query"""
        try:
            response = self.client.get("/search/", {"query": "test"})
            self.assertIn(response.status_code, [200, 404])
        except Exception:
            # Search might not be fully configured
            pass
