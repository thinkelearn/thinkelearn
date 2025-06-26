#!/usr/bin/env python
"""
Script to create initial pages in production after deployment.
This should be run once after the first deployment with new page models.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'thinkelearn.settings.production')
django.setup()

from wagtail.models import Page, Site
from home.models import HomePage, AboutPage, ContactPage, PortfolioIndexPage, ContactFormField
from blog.models import BlogIndexPage

def setup_production_pages():
    """Create initial pages if they don't exist"""
    print("🔧 Setting up production pages...")
    
    try:
        # Get the HomePage (site root)
        home_page = HomePage.objects.first()
        if not home_page:
            print("❌ No HomePage found. Please ensure the site is properly set up.")
            return False
            
        print(f"✅ Found HomePage: {home_page.title}")
        
        pages_created = 0
        
        # Create About page if it doesn't exist
        if not AboutPage.objects.exists():
            about_page = AboutPage(
                title='About Us',
                slug='about',
                hero_title='About THINK eLearn',
                hero_subtitle='Empowering educational institutions with innovative technology solutions that transform learning experiences.',
                story_title='Our Story',
                story_content='<p>THINK eLearn was founded with a simple mission: to bridge the gap between traditional education and modern technology. We believe that every learner deserves access to innovative, engaging, and effective educational tools.</p>',
                mission_title='Our Mission',
                mission_content='<p>We empower educational institutions with cutting-edge technology solutions that enhance learning outcomes, improve student engagement, and streamline educational processes.</p>',
            )
            home_page.add_child(instance=about_page)
            about_page.save_revision().publish()
            print("✅ Created About page")
            pages_created += 1
        
        # Create Contact page if it doesn't exist
        if not ContactPage.objects.exists():
            contact_page = ContactPage(
                title='Contact',
                slug='contact',
                hero_title='Contact Us',
                hero_subtitle='Ready to transform your educational technology? Get in touch to discuss your needs.',
                intro_text='<p>We\'d love to hear from you. Send us a message and we\'ll respond as soon as possible.</p>',
                to_address='info@thinkelearn.com',
                from_address='noreply@thinkelearn.com',
                subject='New Contact Form Submission from thinkelearn.com',
                phone='+1 (555) 123-4567',
                email='info@thinkelearn.com',
                address='123 Education Blvd\nSuite 100\nTech City, TC 12345',
                office_hours='Monday - Friday: 9:00 AM - 6:00 PM\nSaturday: 10:00 AM - 4:00 PM\nSunday: Closed',
            )
            home_page.add_child(instance=contact_page)
            contact_page.save_revision().publish()
            
            # Create form fields for contact page
            ContactFormField.objects.create(page=contact_page, sort_order=1, label='Name', field_type='singleline', required=True)
            ContactFormField.objects.create(page=contact_page, sort_order=2, label='Email', field_type='email', required=True)
            ContactFormField.objects.create(page=contact_page, sort_order=3, label='Subject', field_type='singleline', required=True)
            ContactFormField.objects.create(page=contact_page, sort_order=4, label='Message', field_type='multiline', required=True)
            
            print("✅ Created Contact page with form fields")
            pages_created += 1
        
        # Create Blog index page if it doesn't exist
        if not BlogIndexPage.objects.exists():
            blog_page = BlogIndexPage(
                title='Blog',
                slug='blog',
                intro='<p>Stay updated with our latest insights on educational technology, learning methodologies, and industry trends. Discover how we\'re shaping the future of education.</p>',
            )
            home_page.add_child(instance=blog_page)
            blog_page.save_revision().publish()
            print("✅ Created Blog page")
            pages_created += 1
        
        # Create Portfolio index page if it doesn't exist
        if not PortfolioIndexPage.objects.exists():
            portfolio_page = PortfolioIndexPage(
                title='Portfolio',
                slug='portfolio',
                intro='<p>Explore our successful projects and case studies showcasing innovative educational technology solutions. See how we\'ve helped institutions transform their learning environments.</p>',
            )
            home_page.add_child(instance=portfolio_page)
            portfolio_page.save_revision().publish()
            print("✅ Created Portfolio page")
            pages_created += 1
        
        print(f"\n🎉 Setup complete! Created {pages_created} new pages.")
        print("🌐 Your site is now ready with all core pages:")
        print("   • / (Homepage)")
        print("   • /about/ (About Us)")
        print("   • /contact/ (Contact)")
        print("   • /blog/ (Blog)")
        print("   • /portfolio/ (Portfolio)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting up pages: {e}")
        return False

if __name__ == '__main__':
    success = setup_production_pages()
    sys.exit(0 if success else 1)