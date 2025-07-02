from django.test import RequestFactory, TestCase
from wagtail.models import Page
from wagtail_factories import PageFactory

from home.models import (
    AboutPage,
    ContactPage,
    HomePage,
    PortfolioIndexPage,
    ProjectCategory,
    ProjectPage,
)


class HomePageFactory(PageFactory):
    class Meta:
        model = HomePage

    title = "Test Home Page"
    hero_title = "Test Hero Title"
    hero_subtitle = "Test Hero Subtitle"
    hero_cta_text = "Get Started"
    features_title = "Why Choose Us"
    testimonials_title = "What Clients Say"
    recent_posts_title = "Latest Posts"


class AboutPageFactory(PageFactory):
    class Meta:
        model = AboutPage

    title = "About Us"
    hero_title = "About Test Company"
    story_title = "Our Story"
    mission_title = "Our Mission"


class ContactPageFactory(PageFactory):
    class Meta:
        model = ContactPage

    title = "Contact Us"
    hero_title = "Get In Touch"
    phone = "+1-555-0123"
    email = "test@example.com"


class PortfolioIndexPageFactory(PageFactory):
    class Meta:
        model = PortfolioIndexPage

    title = "Portfolio"
    intro = "Check out our projects"


class ProjectPageFactory(PageFactory):
    class Meta:
        model = ProjectPage

    title = "Test Project"
    project_date = "2024-01-15"
    client_name = "Test Client"
    intro = "Test project introduction"
    description = "Test project description"
    technologies = "Python, Django, React"


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
        homepage = HomePageFactory(parent=self.root_page)
        recent_posts = homepage.get_recent_posts()
        self.assertEqual(len(recent_posts), 0)

    def test_get_recent_posts_disabled(self):
        """Test custom method when feature is disabled"""
        homepage = HomePageFactory(parent=self.root_page, show_recent_posts=False)
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


class ProjectCategoryTest(TestCase):
    def test_category_str_method(self):
        """Test custom string representation"""
        category = ProjectCategory(name="Web Development", slug="web-dev")
        self.assertEqual(str(category), "Web Development")


class PortfolioIndexPageTest(TestCase):
    def setUp(self):
        self.root_page = Page.add_root(title="Root")
        self.factory = RequestFactory()

    def test_get_context_with_no_projects(self):
        """Test custom context method when no projects exist"""
        portfolio = PortfolioIndexPageFactory(parent=self.root_page)
        request = self.factory.get("/")
        context = portfolio.get_context(request)
        self.assertIn("projects", context)
        self.assertEqual(len(context["projects"]), 0)


class ProjectPageTest(TestCase):
    def setUp(self):
        self.root_page = Page.add_root(title="Root")
        self.factory = RequestFactory()

    def test_project_defaults(self):
        """Test custom default values for business requirements"""
        project = ProjectPage(title="Test")
        self.assertEqual(project.results_title, "Results & Impact")
        self.assertEqual(project.challenge_title, "The Challenge")
        self.assertEqual(project.solution_title, "Our Solution")

    def test_get_technologies_list(self):
        """Test custom method for parsing technologies string"""
        project = ProjectPageFactory(
            parent=self.root_page, technologies="Python, Django, React, Vue.js"
        )
        tech_list = project.get_technologies_list()
        expected = ["Python", "Django", "React", "Vue.js"]
        self.assertEqual(tech_list, expected)

    def test_get_technologies_list_empty(self):
        """Test custom method edge case with empty technologies"""
        project = ProjectPageFactory(parent=self.root_page, technologies="")
        tech_list = project.get_technologies_list()
        self.assertEqual(tech_list, [])

    def test_get_context_related_projects(self):
        """Test custom context method for related projects"""
        # Create a category
        category = ProjectCategory.objects.create(name="Web", slug="web")

        # Create main project
        project = ProjectPageFactory(parent=self.root_page)
        project.categories.add(category)

        # Create related project
        related_project = ProjectPageFactory(
            parent=self.root_page, title="Related Project"
        )
        related_project.categories.add(category)

        request = self.factory.get("/")
        context = project.get_context(request)
        self.assertIn("related_projects", context)
        # Should exclude self from related projects
        self.assertNotIn(project, context["related_projects"])
