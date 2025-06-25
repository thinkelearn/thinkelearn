from django.db import models

from wagtail.models import Page
from wagtail.fields import StreamField
from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock
from wagtail.admin.panels import FieldPanel, MultiFieldPanel


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
        
        # This will be implemented when we create the blog app
        # For now, return empty list
        return []

    class Meta:
        verbose_name = "Home Page"
