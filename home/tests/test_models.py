import factory
from django.test import TestCase
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase
from wagtail_factories import PageFactory

from home.models import (
    AboutPage,
    ContactFormField,
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


class ProjectCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProjectCategory

    name = factory.Sequence(lambda n: f"Category {n}")
    slug = factory.Sequence(lambda n: f"category-{n}")
    description = "Test category description"


class PortfolioIndexPageFactory(PageFactory):
    class Meta:
        model = PortfolioIndexPage

    title = "Portfolio"
    intro = "<p>Our portfolio of work</p>"


class ProjectPageFactory(PageFactory):
    class Meta:
        model = ProjectPage

    title = factory.Sequence(lambda n: f"Project {n}")
    project_date = factory.Faker("date_this_year")
    client_name = factory.Faker("company")
    intro = factory.Faker("sentence", nb_words=20)
    description = factory.Faker("text")
    technologies = "Python, Django, React"


class HomePageTest(WagtailPageTestCase):
    def setUp(self):
        # Use wagtail's built-in root page setup
        self.root_page = Page.get_first_root_node()

    def test_can_create_homepage(self):
        homepage = HomePageFactory(parent=self.root_page)
        self.assertIsInstance(homepage, HomePage)
        self.assertEqual(homepage.title, "Test Home Page")

    def test_homepage_fields(self):
        homepage = HomePageFactory(
            parent=self.root_page,
            hero_title="Custom Hero",
            hero_subtitle="Custom Subtitle",
            features_title="Custom Features",
        )

        self.assertEqual(homepage.hero_title, "Custom Hero")
        self.assertEqual(homepage.hero_subtitle, "Custom Subtitle")
        self.assertEqual(homepage.features_title, "Custom Features")

    def test_homepage_defaults(self):
        homepage = HomePage(title="Test")
        self.assertEqual(homepage.hero_title, "Empowering Learning Through Innovation")
        self.assertEqual(homepage.hero_cta_text, "Get Started")
        self.assertEqual(homepage.features_title, "Why Choose THINK eLearn")

    def test_get_recent_posts_with_no_blog(self):
        homepage = HomePageFactory(parent=self.root_page)
        recent_posts = homepage.get_recent_posts()
        self.assertEqual(len(recent_posts), 0)

    def test_get_recent_posts_disabled(self):
        homepage = HomePageFactory(parent=self.root_page, show_recent_posts=False)
        recent_posts = homepage.get_recent_posts()
        self.assertEqual(len(recent_posts), 0)

    def test_homepage_subpage_types(self):
        self.assertIn("home.AboutPage", HomePage.subpage_types)
        self.assertIn("home.ContactPage", HomePage.subpage_types)
        self.assertIn("home.PortfolioIndexPage", HomePage.subpage_types)
        self.assertIn("blog.BlogIndexPage", HomePage.subpage_types)

    def test_homepage_parent_page_types(self):
        self.assertEqual(HomePage.parent_page_types, [])


class AboutPageTest(WagtailPageTestCase):
    def setUp(self):
        self.root_page = Page.objects.get(id=2)

    def test_can_create_about_page(self):
        about_page = AboutPageFactory(parent=self.root_page)
        self.assertIsInstance(about_page, AboutPage)
        self.assertEqual(about_page.title, "About Us")

    def test_about_page_defaults(self):
        about_page = AboutPage(title="About")
        self.assertEqual(about_page.hero_title, "About THINK eLearn")
        self.assertEqual(about_page.story_title, "Our Story")
        self.assertEqual(about_page.mission_title, "Our Mission")

    def test_about_page_constraints(self):
        self.assertEqual(AboutPage.parent_page_types, [])
        self.assertEqual(AboutPage.subpage_types, [])


class ContactPageTest(WagtailPageTestCase):
    def setUp(self):
        self.root_page = Page.objects.get(id=2)

    def test_can_create_contact_page(self):
        contact_page = ContactPageFactory(parent=self.root_page)
        self.assertIsInstance(contact_page, ContactPage)
        self.assertEqual(contact_page.phone, "+1-555-0123")
        self.assertEqual(contact_page.email, "test@example.com")

    def test_contact_page_defaults(self):
        contact_page = ContactPage(title="Contact")
        self.assertEqual(contact_page.hero_title, "Contact Us")
        self.assertTrue(contact_page.show_contact_info)
        self.assertTrue(contact_page.show_faq)

    def test_contact_form_field_creation(self):
        contact_page = ContactPageFactory(parent=self.root_page)
        form_field = ContactFormField(
            page=contact_page,
            label="Test Field",
            field_type="singleline",
            required=True,
        )
        form_field.save()

        self.assertEqual(form_field.page, contact_page)
        self.assertEqual(form_field.label, "Test Field")
        self.assertTrue(form_field.required)


class ProjectCategoryTest(TestCase):
    def test_can_create_category(self):
        category = ProjectCategoryFactory()
        self.assertIsInstance(category, ProjectCategory)
        self.assertTrue(category.name.startswith("Category"))
        self.assertTrue(category.slug.startswith("category-"))

    def test_category_str_method(self):
        category = ProjectCategoryFactory(name="Web Development")
        self.assertEqual(str(category), "Web Development")

    def test_category_slug_unique(self):
        ProjectCategoryFactory(slug="unique-slug")
        with self.assertRaises((ValueError, Exception)):
            ProjectCategoryFactory(slug="unique-slug")


class PortfolioIndexPageTest(WagtailPageTestCase):
    def setUp(self):
        self.root_page = Page.objects.get(id=2)

    def test_can_create_portfolio_index(self):
        portfolio = PortfolioIndexPageFactory(parent=self.root_page)
        self.assertIsInstance(portfolio, PortfolioIndexPage)
        self.assertEqual(portfolio.subpage_types, ["home.ProjectPage"])

    def test_get_context_with_no_projects(self):
        portfolio = PortfolioIndexPageFactory(parent=self.root_page)
        from django.http import HttpRequest

        request = HttpRequest()
        context = portfolio.get_context(request)

        self.assertIn("projects", context)
        self.assertIn("categories", context)
        self.assertEqual(len(context["projects"]), 0)


class ProjectPageTest(WagtailPageTestCase):
    def setUp(self):
        self.root_page = Page.objects.get(id=2)
        self.portfolio_index = PortfolioIndexPageFactory(parent=self.root_page)
        self.category = ProjectCategoryFactory()

    def test_can_create_project_page(self):
        project = ProjectPageFactory(parent=self.portfolio_index)
        self.assertIsInstance(project, ProjectPage)
        self.assertTrue(project.title.startswith("Project"))

    def test_project_page_constraints(self):
        self.assertEqual(ProjectPage.parent_page_types, ["home.PortfolioIndexPage"])
        self.assertEqual(ProjectPage.subpage_types, [])

    def test_get_technologies_list(self):
        project = ProjectPageFactory(
            parent=self.portfolio_index,
            technologies="Python, Django, React, JavaScript",
        )

        technologies = project.get_technologies_list()
        expected = ["Python", "Django", "React", "JavaScript"]
        self.assertEqual(technologies, expected)

    def test_get_technologies_list_empty(self):
        project = ProjectPageFactory(parent=self.portfolio_index, technologies="")
        technologies = project.get_technologies_list()
        self.assertEqual(technologies, [])

    def test_project_search_fields(self):
        search_fields = [field.field_name for field in ProjectPage.search_fields]
        self.assertIn("intro", search_fields)
        self.assertIn("description", search_fields)
        self.assertIn("client_name", search_fields)

    def test_project_defaults(self):
        project = ProjectPage(title="Test Project")
        self.assertEqual(project.results_title, "Results & Impact")
        self.assertEqual(project.challenge_title, "The Challenge")
        self.assertEqual(project.solution_title, "Our Solution")

    def test_get_context_related_projects(self):
        category = ProjectCategoryFactory()

        project1 = ProjectPageFactory(parent=self.portfolio_index)
        project1.categories.add(category)

        project2 = ProjectPageFactory(parent=self.portfolio_index)
        project2.categories.add(category)

        from django.http import HttpRequest

        request = HttpRequest()
        context = project1.get_context(request)

        self.assertIn("related_projects", context)
        related = context["related_projects"]
        self.assertIn(project2, related)
        self.assertNotIn(project1, related)  # Should exclude itself
