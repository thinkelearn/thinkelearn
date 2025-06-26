from django.db import models

from wagtail.models import Page
from wagtail.fields import StreamField, RichTextField
from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.search import index
from wagtail.contrib.forms.models import AbstractEmailForm, AbstractFormField
from wagtail.contrib.forms.panels import FormSubmissionsPanel
from wagtail.snippets.models import register_snippet
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from django import forms


class HomePage(Page):
    # Hero Section
    hero_title = models.CharField(
        max_length=255, 
        default="Empowering Learning Through Innovation",
        help_text="Main headline for the hero section"
    )
    hero_subtitle = models.TextField(
        blank=True,
        help_text="Subtitle text below the main headline"
    )
    hero_image = models.ForeignKey(
        'wagtailimages.Image',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        help_text="Hero background or featured image"
    )
    hero_cta_text = models.CharField(
        max_length=50, 
        default="Get Started",
        help_text="Text for the primary call-to-action button"
    )
    hero_cta_link = models.ForeignKey(
        'wagtailcore.Page',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        help_text="Page to link to from the CTA button"
    )
    
    # Features Section
    features_title = models.CharField(
        max_length=255, 
        default="Why Choose THINK eLearn",
        help_text="Title for the features section"
    )
    features = StreamField([
        ('feature', blocks.StructBlock([
            ('icon', blocks.CharBlock(
                help_text="Font Awesome icon class (e.g., 'fas fa-graduation-cap')"
            )),
            ('title', blocks.CharBlock(max_length=100)),
            ('description', blocks.TextBlock()),
        ]))
    ], blank=True, use_json_field=True)
    
    # Testimonials
    testimonials_title = models.CharField(
        max_length=255,
        default="What Our Clients Say",
        help_text="Title for the testimonials section"
    )
    testimonials = StreamField([
        ('testimonial', blocks.StructBlock([
            ('quote', blocks.TextBlock()),
            ('author', blocks.CharBlock(max_length=100)),
            ('company', blocks.CharBlock(max_length=100, required=False)),
            ('avatar', ImageChooserBlock(required=False)),
        ]))
    ], blank=True, use_json_field=True)
    
    # Recent Blog Posts
    show_recent_posts = models.BooleanField(
        default=True,
        help_text="Show recent blog posts on the homepage"
    )
    recent_posts_title = models.CharField(
        max_length=255,
        default="Latest Insights",
        help_text="Title for the recent posts section"
    )
    recent_posts_count = models.IntegerField(
        default=3,
        help_text="Number of recent posts to display"
    )

    content_panels = Page.content_panels + [
        MultiFieldPanel([
            FieldPanel('hero_title'),
            FieldPanel('hero_subtitle'),
            FieldPanel('hero_image'),
            FieldPanel('hero_cta_text'),
            FieldPanel('hero_cta_link'),
        ], heading="Hero Section"),
        
        MultiFieldPanel([
            FieldPanel('features_title'),
            FieldPanel('features'),
        ], heading="Features Section"),
        
        MultiFieldPanel([
            FieldPanel('testimonials_title'),
            FieldPanel('testimonials'),
        ], heading="Testimonials"),
        
        MultiFieldPanel([
            FieldPanel('show_recent_posts'),
            FieldPanel('recent_posts_title'),
            FieldPanel('recent_posts_count'),
        ], heading="Recent Posts Section"),
    ]

    def get_recent_posts(self):
        """Get recent blog posts for the homepage"""
        if not self.show_recent_posts:
            return []
        
        from blog.models import BlogPage
        return BlogPage.objects.live().order_by('-first_published_at')[:self.recent_posts_count]

    class Meta:
        verbose_name = "Home Page"


class AboutPage(Page):
    # Hero Section
    hero_title = models.CharField(
        max_length=255,
        default="About THINK eLearn",
        help_text="Main headline for the about page"
    )
    hero_subtitle = models.TextField(
        blank=True,
        help_text="Subtitle text below the main headline"
    )
    hero_image = models.ForeignKey(
        'wagtailimages.Image',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        help_text="Hero background or team image"
    )
    
    # Company Story
    story_title = models.CharField(
        max_length=255,
        default="Our Story",
        help_text="Title for the company story section"
    )
    story_content = RichTextField(
        blank=True,
        help_text="Rich text content about the company story"
    )
    
    # Mission & Values
    mission_title = models.CharField(
        max_length=255,
        default="Our Mission",
        help_text="Title for the mission section"
    )
    mission_content = RichTextField(
        blank=True,
        help_text="Rich text content about the company mission"
    )
    
    values_title = models.CharField(
        max_length=255,
        default="Our Values",
        help_text="Title for the values section"
    )
    values = StreamField([
        ('value', blocks.StructBlock([
            ('icon', blocks.CharBlock(
                help_text="Font Awesome icon class (e.g., 'fas fa-heart')"
            )),
            ('title', blocks.CharBlock(max_length=100)),
            ('description', blocks.TextBlock()),
        ]))
    ], blank=True, use_json_field=True)
    
    # Team Section
    team_title = models.CharField(
        max_length=255,
        default="Meet Our Team",
        help_text="Title for the team section"
    )
    team_members = StreamField([
        ('member', blocks.StructBlock([
            ('name', blocks.CharBlock(max_length=100)),
            ('role', blocks.CharBlock(max_length=100)),
            ('bio', blocks.TextBlock()),
            ('photo', ImageChooserBlock(required=False)),
            ('linkedin', blocks.URLBlock(required=False, help_text="LinkedIn profile URL")),
            ('twitter', blocks.URLBlock(required=False, help_text="Twitter profile URL")),
            ('email', blocks.EmailBlock(required=False)),
        ]))
    ], blank=True, use_json_field=True)
    
    # Timeline/Milestones
    timeline_title = models.CharField(
        max_length=255,
        default="Our Journey",
        help_text="Title for the timeline section"
    )
    milestones = StreamField([
        ('milestone', blocks.StructBlock([
            ('year', blocks.CharBlock(max_length=4, help_text="Year (e.g., '2020')")),
            ('title', blocks.CharBlock(max_length=100)),
            ('description', blocks.TextBlock()),
        ]))
    ], blank=True, use_json_field=True)

    content_panels = Page.content_panels + [
        MultiFieldPanel([
            FieldPanel('hero_title'),
            FieldPanel('hero_subtitle'),
            FieldPanel('hero_image'),
        ], heading="Hero Section"),
        
        MultiFieldPanel([
            FieldPanel('story_title'),
            FieldPanel('story_content'),
        ], heading="Company Story"),
        
        MultiFieldPanel([
            FieldPanel('mission_title'),
            FieldPanel('mission_content'),
        ], heading="Mission"),
        
        MultiFieldPanel([
            FieldPanel('values_title'),
            FieldPanel('values'),
        ], heading="Values"),
        
        MultiFieldPanel([
            FieldPanel('team_title'),
            FieldPanel('team_members'),
        ], heading="Team"),
        
        MultiFieldPanel([
            FieldPanel('timeline_title'),
            FieldPanel('milestones'),
        ], heading="Timeline/Milestones"),
    ]

    class Meta:
        verbose_name = "About Page"


class ContactFormField(AbstractFormField):
    page = ParentalKey('ContactPage', on_delete=models.CASCADE, related_name='form_fields')


class ContactPage(AbstractEmailForm):
    # Hero Section
    hero_title = models.CharField(
        max_length=255,
        default="Contact Us",
        help_text="Main headline for the contact page"
    )
    hero_subtitle = models.TextField(
        blank=True,
        help_text="Subtitle text below the main headline"
    )
    
    # Introduction
    intro_text = RichTextField(
        blank=True,
        help_text="Introduction text above the contact form"
    )
    
    # Contact Information
    show_contact_info = models.BooleanField(
        default=True,
        help_text="Display contact information section"
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Phone number"
    )
    email = models.EmailField(
        blank=True,
        help_text="Contact email address"
    )
    address = models.TextField(
        blank=True,
        help_text="Office address"
    )
    
    # Office Hours
    office_hours = models.TextField(
        blank=True,
        help_text="Office hours information"
    )
    
    # Social Media
    linkedin_url = models.URLField(blank=True, help_text="LinkedIn profile URL")
    twitter_url = models.URLField(blank=True, help_text="Twitter profile URL")
    facebook_url = models.URLField(blank=True, help_text="Facebook page URL")
    
    # FAQ Section
    show_faq = models.BooleanField(
        default=True,
        help_text="Display FAQ section"
    )
    faq_title = models.CharField(
        max_length=255,
        default="Frequently Asked Questions",
        help_text="Title for the FAQ section"
    )
    faqs = StreamField([
        ('faq', blocks.StructBlock([
            ('question', blocks.CharBlock(max_length=200)),
            ('answer', blocks.TextBlock()),
        ]))
    ], blank=True, use_json_field=True)
    
    # Form Settings
    thank_you_text = RichTextField(
        blank=True,
        help_text="Thank you message shown after form submission"
    )

    content_panels = AbstractEmailForm.content_panels + [
        MultiFieldPanel([
            FieldPanel('hero_title'),
            FieldPanel('hero_subtitle'),
        ], heading="Hero Section"),
        
        FieldPanel('intro_text'),
        
        MultiFieldPanel([
            FieldPanel('show_contact_info'),
            FieldPanel('phone'),
            FieldPanel('email'),
            FieldPanel('address'),
            FieldPanel('office_hours'),
        ], heading="Contact Information"),
        
        MultiFieldPanel([
            FieldPanel('linkedin_url'),
            FieldPanel('twitter_url'),
            FieldPanel('facebook_url'),
        ], heading="Social Media"),
        
        MultiFieldPanel([
            FieldPanel('show_faq'),
            FieldPanel('faq_title'),
            FieldPanel('faqs'),
        ], heading="FAQ Section"),
        
        FieldPanel('thank_you_text'),
        
        MultiFieldPanel([
            FieldPanel('to_address'),
            FieldPanel('from_address'),
            FieldPanel('subject'),
        ], heading="Email Settings"),
        
        FormSubmissionsPanel(),
    ]

    class Meta:
        verbose_name = "Contact Page"


class PortfolioIndexPage(Page):
    intro = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('intro')
    ]

    def get_context(self, request):
        # Update context to include only published projects, ordered by reverse-chron
        context = super().get_context(request)
        projects = self.get_children().live().order_by('-first_published_at')
        
        # Filter by category if provided
        category = request.GET.get('category')
        if category:
            projects = projects.filter(projectpage__categories__slug=category)
        
        context['projects'] = projects
        context['categories'] = ProjectCategory.objects.all()
        return context


@register_snippet
class ProjectCategory(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=80)
    description = models.TextField(blank=True)

    panels = [
        FieldPanel('name'),
        FieldPanel('slug'),
        FieldPanel('description'),
    ]

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Project Categories'


class ProjectPage(Page):
    # Basic Info
    project_date = models.DateField("Project completion date")
    client_name = models.CharField(max_length=200, blank=True)
    project_url = models.URLField(blank=True, help_text="Live project URL")
    intro = models.CharField(max_length=250)
    description = RichTextField(blank=True)
    
    # Images
    featured_image = models.ForeignKey(
        'wagtailimages.Image',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )
    
    # Project Details
    categories = ParentalManyToManyField('home.ProjectCategory', blank=True)
    technologies = models.TextField(
        blank=True,
        help_text="Comma-separated list of technologies used"
    )
    
    # Results & Metrics
    results_title = models.CharField(
        max_length=255,
        default="Results & Impact",
        help_text="Title for the results section"
    )
    results = StreamField([
        ('metric', blocks.StructBlock([
            ('label', blocks.CharBlock(max_length=100)),
            ('value', blocks.CharBlock(max_length=50)),
            ('description', blocks.TextBlock(required=False)),
        ]))
    ], blank=True, use_json_field=True)
    
    # Case Study Sections
    challenge_title = models.CharField(
        max_length=255,
        default="The Challenge",
        help_text="Title for the challenge section"
    )
    challenge_content = RichTextField(blank=True)
    
    solution_title = models.CharField(
        max_length=255,
        default="Our Solution",
        help_text="Title for the solution section"
    )
    solution_content = RichTextField(blank=True)
    
    # Testimonial
    testimonial_quote = models.TextField(blank=True)
    testimonial_author = models.CharField(max_length=100, blank=True)
    testimonial_company = models.CharField(max_length=100, blank=True)
    testimonial_avatar = models.ForeignKey(
        'wagtailimages.Image',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )

    search_fields = Page.search_fields + [
        index.SearchField('intro'),
        index.SearchField('description'),
        index.SearchField('client_name'),
    ]

    content_panels = Page.content_panels + [
        MultiFieldPanel([
            FieldPanel('project_date'),
            FieldPanel('client_name'),
            FieldPanel('project_url'),
            FieldPanel('categories', widget=forms.CheckboxSelectMultiple),
            FieldPanel('technologies'),
        ], heading="Project Information"),
        
        FieldPanel('intro'),
        FieldPanel('description'),
        FieldPanel('featured_image'),
        
        MultiFieldPanel([
            FieldPanel('challenge_title'),
            FieldPanel('challenge_content'),
        ], heading="Challenge"),
        
        MultiFieldPanel([
            FieldPanel('solution_title'),
            FieldPanel('solution_content'),
        ], heading="Solution"),
        
        MultiFieldPanel([
            FieldPanel('results_title'),
            FieldPanel('results'),
        ], heading="Results & Metrics"),
        
        MultiFieldPanel([
            FieldPanel('testimonial_quote'),
            FieldPanel('testimonial_author'),
            FieldPanel('testimonial_company'),
            FieldPanel('testimonial_avatar'),
        ], heading="Client Testimonial"),
    ]

    def get_technologies_list(self):
        """Return technologies as a list"""
        if self.technologies:
            return [tech.strip() for tech in self.technologies.split(',')]
        return []

    def get_context(self, request):
        context = super().get_context(request)
        
        # Get related projects (same categories)
        related_projects = ProjectPage.objects.live().exclude(id=self.id)
        if self.categories.exists():
            related_projects = related_projects.filter(categories__in=self.categories.all())
        
        context['related_projects'] = related_projects.distinct()[:3]
        return context
