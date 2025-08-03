from datetime import date

from django.test import RequestFactory, TestCase
from wagtail.models import Page

from portfolio.models import PortfolioIndexPage, ProjectCategory, ProjectPage


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
        portfolio = PortfolioIndexPage(title="Portfolio", slug="portfolio")
        self.root_page.add_child(instance=portfolio)

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
        portfolio = PortfolioIndexPage(title="Portfolio", slug="portfolio")
        self.root_page.add_child(instance=portfolio)

        project = ProjectPage(
            title="Test Project",
            slug="test-project",
            project_date=date.today(),
            intro="Test intro",
            technologies="Python, Django, React, Vue.js",
        )
        portfolio.add_child(instance=project)

        tech_list = project.get_technologies_list()
        expected = ["Python", "Django", "React", "Vue.js"]
        self.assertEqual(tech_list, expected)

    def test_get_technologies_list_empty(self):
        """Test technologies list when no technologies specified"""
        portfolio = PortfolioIndexPage(title="Portfolio", slug="portfolio")
        self.root_page.add_child(instance=portfolio)

        project = ProjectPage(
            title="Test Project",
            slug="test-project",
            project_date=date.today(),
            intro="Test intro",
            technologies="",
        )
        portfolio.add_child(instance=project)

        tech_list = project.get_technologies_list()
        self.assertEqual(tech_list, [])

    def test_get_context_with_related_projects(self):
        """Test custom context method includes related projects"""
        portfolio = PortfolioIndexPage(title="Portfolio", slug="portfolio")
        self.root_page.add_child(instance=portfolio)

        project = ProjectPage(
            title="Test Project",
            slug="test-project",
            project_date=date.today(),
            intro="Test intro",
        )
        portfolio.add_child(instance=project)

        request = self.factory.get("/")
        context = project.get_context(request)

        self.assertIn("related_projects", context)
        # Should be empty since no other projects exist
        self.assertEqual(len(context["related_projects"]), 0)
