from django.core.management.base import BaseCommand
from wagtail.models import Page
from home.models import HomePage, AboutPage, ContactPage, PortfolioIndexPage, ContactFormField
from blog.models import BlogIndexPage


class Command(BaseCommand):
    help = 'Set up initial pages for production deployment'

    def handle(self, *args, **options):
        self.stdout.write("🔧 Setting up production pages...")
        
        # Get the HomePage (site root)
        home_page = HomePage.objects.first()
        if not home_page:
            self.stdout.write(self.style.ERROR("No HomePage found. Please ensure the site is properly set up."))
            return
            
        self.stdout.write(f"✅ Found HomePage: {home_page.title}")
        
        pages_created = 0
        
        # Create About page if it doesn't exist
        if not AboutPage.objects.exists():
            about_page = AboutPage(
                title='About Us',
                slug='about',
                hero_title='About THINK eLearn',
                hero_subtitle='Empowering educational institutions with innovative technology solutions.',
                story_title='Our Story',
                story_content='<p>THINK eLearn was founded with a mission to bridge the gap between traditional education and modern technology.</p>',
                mission_title='Our Mission',
                mission_content='<p>We empower educational institutions with cutting-edge technology solutions that enhance learning outcomes.</p>',
            )
            home_page.add_child(instance=about_page)
            about_page.save_revision().publish()
            self.stdout.write("✅ Created About page")
            pages_created += 1
        
        # Create Contact page if it doesn't exist
        if not ContactPage.objects.exists():
            contact_page = ContactPage(
                title='Contact',
                slug='contact',
                hero_title='Contact Us',
                hero_subtitle='Ready to transform your educational technology? Get in touch.',
                to_address='hello@thinkelearn.com',
                from_address='noreply@thinkelearn.com',
                subject='New Contact Form Submission',
                phone='+1 (289) 816-3749',
                email='hello@thinkelearn.com',
            )
            home_page.add_child(instance=contact_page)
            contact_page.save_revision().publish()
            
            # Create form fields
            ContactFormField.objects.create(page=contact_page, sort_order=1, label='Name', field_type='singleline', required=True)
            ContactFormField.objects.create(page=contact_page, sort_order=2, label='Email', field_type='email', required=True)
            ContactFormField.objects.create(page=contact_page, sort_order=3, label='Subject', field_type='singleline', required=True)
            ContactFormField.objects.create(page=contact_page, sort_order=4, label='Message', field_type='multiline', required=True)
            
            self.stdout.write("✅ Created Contact page with form fields")
            pages_created += 1
        
        # Create Blog index page if it doesn't exist
        if not BlogIndexPage.objects.exists():
            blog_page = BlogIndexPage(
                title='Blog',
                slug='blog',
                intro='<p>Stay updated with our latest insights on educational technology and industry trends.</p>',
            )
            home_page.add_child(instance=blog_page)
            blog_page.save_revision().publish()
            self.stdout.write("✅ Created Blog page")
            pages_created += 1
        
        # Create Portfolio index page if it doesn't exist
        if not PortfolioIndexPage.objects.exists():
            portfolio_page = PortfolioIndexPage(
                title='Portfolio',
                slug='portfolio',
                intro='<p>Explore our successful projects and case studies showcasing innovative educational technology solutions.</p>',
            )
            home_page.add_child(instance=portfolio_page)
            portfolio_page.save_revision().publish()
            self.stdout.write("✅ Created Portfolio page")
            pages_created += 1
        
        self.stdout.write(self.style.SUCCESS(f"\n🎉 Setup complete! Created {pages_created} new pages."))
        self.stdout.write("🌐 Your site is now ready with all core pages!")