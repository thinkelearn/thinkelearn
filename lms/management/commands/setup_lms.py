"""Management command to set up LMS structure and sample data"""

from django.core.management.base import BaseCommand
from wagtail.models import Site

from lms.models import (
    CourseCategory,
    CoursesIndexPage,
    CourseTag,
    LearnerDashboardPage,
)


class Command(BaseCommand):
    help = "Set up LMS structure with courses index and dashboard pages"

    def add_arguments(self, parser):
        parser.add_argument(
            "--with-categories",
            action="store_true",
            help="Create default course categories",
        )
        parser.add_argument(
            "--with-tags",
            action="store_true",
            help="Create default course tags",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Setting up LMS structure..."))

        # Get the home page
        try:
            site = Site.objects.get(is_default_site=True)
            home_page = site.root_page
        except Site.DoesNotExist:
            self.stdout.write(
                self.style.ERROR("No default site found. Please create a site first.")
            )
            return

        # Create CoursesIndexPage if it doesn't exist under this home page
        courses_page = CoursesIndexPage.objects.child_of(home_page).first()
        if not courses_page:
            courses_page = CoursesIndexPage(
                title="Courses",
                slug="courses",
                intro="<p>Explore our comprehensive course catalogue. Learn at your own pace with expert-led SCORM courses.</p>",
            )
            home_page.add_child(instance=courses_page)
            courses_page.save_revision().publish()
            self.stdout.write(
                self.style.SUCCESS(f"✓ Created Courses page at {courses_page.url}")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"→ Courses page already exists at {courses_page.url}"
                )
            )

        # Create LearnerDashboardPage if it doesn't exist under this home page
        dashboard_page = LearnerDashboardPage.objects.child_of(home_page).first()
        if not dashboard_page:
            dashboard_page = LearnerDashboardPage(
                title="My Dashboard",
                slug="dashboard",
                intro="<p>Welcome to your learning dashboard! Track your progress and continue your learning journey.</p>",
            )
            home_page.add_child(instance=dashboard_page)
            dashboard_page.save_revision().publish()
            self.stdout.write(
                self.style.SUCCESS(f"✓ Created Dashboard page at {dashboard_page.url}")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"→ Dashboard page already exists at {dashboard_page.url}"
                )
            )

        # Create default categories if requested
        if options["with_categories"]:
            self.create_default_categories()

        # Create default tags if requested
        if options["with_tags"]:
            self.create_default_tags()

        self.stdout.write(
            self.style.SUCCESS(
                "\n✓ LMS setup complete! You can now create courses under the Courses page."
            )
        )

    def create_default_categories(self):
        """Create default course categories"""
        categories_data = [
            {
                "name": "Programming",
                "slug": "programming",
                "description": "Learn programming languages, frameworks, and software development",
                "icon": "fa-code",
            },
            {
                "name": "Web Development",
                "slug": "web-development",
                "description": "Master modern web development technologies",
                "icon": "fa-laptop-code",
            },
            {
                "name": "Data Science",
                "slug": "data-science",
                "description": "Explore data analysis, machine learning, and AI",
                "icon": "fa-chart-line",
            },
            {
                "name": "Design",
                "slug": "design",
                "description": "Learn UI/UX design, graphic design, and visual communication",
                "icon": "fa-palette",
            },
            {
                "name": "Business",
                "slug": "business",
                "description": "Develop business skills, management, and entrepreneurship",
                "icon": "fa-briefcase",
            },
            {
                "name": "Cybersecurity",
                "slug": "cybersecurity",
                "description": "Learn security best practices and ethical hacking",
                "icon": "fa-shield-alt",
            },
        ]

        self.stdout.write("\nCreating default categories...")
        for data in categories_data:
            category, created = CourseCategory.objects.get_or_create(
                slug=data["slug"],
                defaults={
                    "name": data["name"],
                    "description": data["description"],
                    "icon": data["icon"],
                },
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Created category: {data['name']}")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"  → Category already exists: {data['name']}")
                )

    def create_default_tags(self):
        """Create default course tags"""
        tags_data = [
            # Programming languages
            ("Python", "python"),
            ("JavaScript", "javascript"),
            ("Java", "java"),
            ("C#", "csharp"),
            ("Ruby", "ruby"),
            ("PHP", "php"),
            ("Go", "go"),
            # Web technologies
            ("HTML", "html"),
            ("CSS", "css"),
            ("React", "react"),
            ("Vue.js", "vue"),
            ("Angular", "angular"),
            ("Node.js", "nodejs"),
            ("Django", "django"),
            # Data & AI
            ("Machine Learning", "machine-learning"),
            ("Deep Learning", "deep-learning"),
            ("Data Analysis", "data-analysis"),
            ("SQL", "sql"),
            ("MongoDB", "mongodb"),
            # Design
            ("UI Design", "ui-design"),
            ("UX Design", "ux-design"),
            ("Figma", "figma"),
            ("Adobe XD", "adobe-xd"),
            # Other
            ("DevOps", "devops"),
            ("Docker", "docker"),
            ("Kubernetes", "kubernetes"),
            ("AWS", "aws"),
            ("Azure", "azure"),
            ("Git", "git"),
        ]

        self.stdout.write("\nCreating default tags...")
        for name, slug in tags_data:
            tag, created = CourseTag.objects.get_or_create(
                slug=slug,
                defaults={"name": name},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"  ✓ Created tag: {name}"))
            else:
                self.stdout.write(self.style.WARNING(f"  → Tag already exists: {name}"))
