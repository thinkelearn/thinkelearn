#!/usr/bin/env python
"""
Simple script to verify deployment status and page availability.
Can be run locally or in production to check if everything is working.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'thinkelearn.settings.production')
django.setup()

from wagtail.models import Page, Site
from home.models import HomePage, AboutPage, ContactPage, PortfolioIndexPage
from blog.models import BlogIndexPage

def verify_deployment():
    """Verify that all pages and functionality are working"""
    print("🔍 Verifying deployment...")
    
    issues = []
    
    try:
        # Check database connection
        Page.objects.count()
        print("✅ Database connection: OK")
    except Exception as e:
        issues.append(f"Database connection failed: {e}")
    
    try:
        # Check site configuration
        site = Site.objects.get(is_default_site=True)
        print(f"✅ Default site: {site.hostname}:{site.port}")
    except Exception as e:
        issues.append(f"Site configuration issue: {e}")
    
    # Check required pages exist
    page_checks = [
        (HomePage, "HomePage"),
        (AboutPage, "About page"),
        (ContactPage, "Contact page"),
        (BlogIndexPage, "Blog page"),
        (PortfolioIndexPage, "Portfolio page"),
    ]
    
    for page_class, name in page_checks:
        if page_class.objects.exists():
            page = page_class.objects.first()
            print(f"✅ {name}: {page.url}")
        else:
            issues.append(f"{name} not found")
    
    # Check contact form
    try:
        contact_page = ContactPage.objects.first()
        if contact_page:
            form_fields = contact_page.form_fields.count()
            if form_fields > 0:
                print(f"✅ Contact form: {form_fields} fields configured")
            else:
                issues.append("Contact form has no fields")
        else:
            issues.append("Contact page not found")
    except Exception as e:
        issues.append(f"Contact form check failed: {e}")
    
    # Summary
    if issues:
        print(f"\n❌ {len(issues)} issues found:")
        for issue in issues:
            print(f"   • {issue}")
        print("\nℹ️  Run setup_production_pages.py to fix missing pages")
        return False
    else:
        print("\n🎉 Deployment verification successful!")
        print("🌐 All pages are configured and ready")
        return True

if __name__ == '__main__':
    success = verify_deployment()
    sys.exit(0 if success else 1)