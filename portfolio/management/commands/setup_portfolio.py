from django.core.management.base import BaseCommand
from wagtail.rich_text import RichText

from home.models import HomePage
from portfolio.models import PortfolioCategory, PortfolioIndexPage


class Command(BaseCommand):
    help = "Set up initial portfolio pages"

    def handle(self, *args, **options):
        self.stdout.write("🎨 Setting up portfolio pages...")

        # Get the HomePage (site root)
        home_page = HomePage.objects.first()
        if not home_page:
            self.stdout.write(
                self.style.ERROR(
                    "No HomePage found. Please ensure the site is properly set up."
                )
            )
            return

        self.stdout.write(f"✅ Found HomePage: {home_page.title}")

        # Create portfolio categories
        categories_created = 0
        categories = [
            {
                "name": "Learning Modules",
                "slug": "learning-modules",
                "description": "Interactive e-learning modules created with Rise, Storyline, and similar tools",
                "icon": "fas fa-graduation-cap",
            },
            {
                "name": "Video Content",
                "slug": "video-content",
                "description": "Educational videos and multimedia presentations",
                "icon": "fas fa-video",
            },
            {
                "name": "Interactive Media",
                "slug": "interactive-media",
                "description": "Animations, simulations, and interactive content",
                "icon": "fas fa-mouse-pointer",
            },
            {
                "name": "Visual Design",
                "slug": "visual-design",
                "description": "Infographics, presentations, and visual learning materials",
                "icon": "fas fa-palette",
            },
        ]

        for cat_data in categories:
            category, created = PortfolioCategory.objects.get_or_create(
                slug=cat_data["slug"],
                defaults={
                    "name": cat_data["name"],
                    "description": cat_data["description"],
                    "icon": cat_data["icon"],
                },
            )
            if created:
                categories_created += 1
                self.stdout.write(f"✅ Created category: {category.name}")

        # Create Portfolio Index page if it doesn't exist
        pages_created = 0
        if not PortfolioIndexPage.objects.exists():
            portfolio_index = PortfolioIndexPage(
                title="Portfolio",
                slug="portfolio",
                hero_title="Our Portfolio",
                hero_subtitle="Explore examples of our educational technology solutions and creative projects.",
                intro=RichText(
                    "<p>Welcome to our portfolio of educational content and technology solutions. "
                    "Here you'll find interactive learning modules, engaging videos, and innovative "
                    "educational resources that demonstrate our capabilities.</p>"
                ),
            )
            home_page.add_child(instance=portfolio_index)
            portfolio_index.save_revision().publish()
            pages_created += 1
            self.stdout.write(f"✅ Created: {portfolio_index.title}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\n🎉 Portfolio setup complete!"
                f"\n📊 Categories created: {categories_created}"
                f"\n📄 Pages created: {pages_created}"
                f"\n🌐 Visit: http://localhost:8000/portfolio/"
            )
        )
