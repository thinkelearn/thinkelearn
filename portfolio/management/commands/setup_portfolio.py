from django.core.management.base import BaseCommand
from wagtail.rich_text import RichText

from home.models import HomePage
from portfolio.models import PortfolioIndexPage


class Command(BaseCommand):
    help = "Set up initial portfolio pages for production deployment"

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

        pages_created = 0

        # Create Portfolio index page if it doesn't exist
        if not PortfolioIndexPage.objects.exists():
            # Check if old portfolio page exists with different content type
            from wagtail.models import Page

            existing_portfolio = Page.objects.filter(slug="portfolio").first()

            if existing_portfolio:
                self.stdout.write(
                    "ℹ️  Found existing portfolio page with old content type - skipping creation"
                )
                self.stdout.write("🔄 Run migrations to update existing portfolio page")
            else:
                portfolio_page = PortfolioIndexPage(
                    title="Portfolio",
                    slug="portfolio",
                    intro=RichText(
                        "<p>Explore our successful projects and case studies showcasing innovative educational technology solutions.</p>"
                    ),
                )
                home_page.add_child(instance=portfolio_page)
                portfolio_page.save_revision().publish()
                self.stdout.write("✅ Created Portfolio page")
                pages_created += 1
        else:
            self.stdout.write("ℹ️  Portfolio page already exists")

        self.stdout.write(
            self.style.SUCCESS(
                f"\n🎉 Portfolio setup complete! Created {pages_created} new pages."
            )
        )
        if pages_created > 0:
            self.stdout.write("🌐 Your portfolio section is now ready!")
