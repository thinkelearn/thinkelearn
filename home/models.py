from django.db import models
from modelcluster.fields import ParentalKey
from wagtail import blocks
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.contrib.forms.models import AbstractEmailForm, AbstractFormField
from wagtail.contrib.forms.panels import FormSubmissionsPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.images.blocks import ImageChooserBlock
from wagtail.models import Page


class ProcessBlock(blocks.StructBlock):
    title = blocks.CharBlock(max_length=255, help_text="Process section title")
    content = blocks.RichTextBlock(help_text="Process description")
    icon = blocks.CharBlock(
        max_length=50,
        default="fas fa-sync-alt",
        help_text="FontAwesome icon class (e.g., 'fas fa-sync-alt', 'fas fa-rocket', 'fas fa-lightbulb')",
    )

    class Meta:
        template = "home/blocks/process_block.html"
        icon = "list-ul"
        label = "Process Section"


class HomePage(Page):
    # Hero Section
    hero_title = models.CharField(
        max_length=255,
        default="Empowering Learning Through Innovation",
        help_text="Main headline for the hero section",
    )
    hero_subtitle = models.TextField(
        blank=True, help_text="Subtitle text below the main headline"
    )
    hero_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Hero background or featured image",
    )
    hero_cta_text = models.CharField(
        max_length=50,
        default="Get Started",
        help_text="Text for the primary call-to-action button",
    )
    hero_cta_link = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Page to link to from the CTA button",
    )

    # Features Section
    features_title = models.CharField(
        max_length=255,
        default="Why Choose THINK eLearn",
        help_text="Title for the features section",
    )
    features_description = models.TextField(
        default="Discover what makes THINK eLearn the perfect partner for your educational technology needs.",
        help_text="Description text for the features section",
    )
    features = StreamField(
        [
            (
                "feature",
                blocks.StructBlock(
                    [
                        (
                            "icon",
                            blocks.CharBlock(
                                help_text="Font Awesome icon class (e.g., 'fas fa-graduation-cap')"
                            ),
                        ),
                        ("title", blocks.CharBlock(max_length=100)),
                        ("description", blocks.TextBlock()),
                    ]
                ),
            )
        ],
        blank=True,
        use_json_field=True,
    )

    # Testimonials
    testimonials_title = models.CharField(
        max_length=255,
        default="What Our Clients Say",
        help_text="Title for the testimonials section",
    )
    testimonials_description = models.TextField(
        default="See what our clients have to say about their experience working with us.",
        help_text="Description text for the testimonials section",
    )
    testimonials = StreamField(
        [
            (
                "testimonial",
                blocks.StructBlock(
                    [
                        ("quote", blocks.TextBlock()),
                        ("author", blocks.CharBlock(max_length=100)),
                        ("company", blocks.CharBlock(max_length=100, required=False)),
                        ("avatar", ImageChooserBlock(required=False)),
                    ]
                ),
            )
        ],
        blank=True,
        use_json_field=True,
    )

    # Recent Blog Posts
    show_recent_posts = models.BooleanField(
        default=True, help_text="Show recent blog posts on the homepage"
    )
    recent_posts_title = models.CharField(
        max_length=255,
        default="Latest Insights",
        help_text="Title for the recent posts section",
    )
    recent_posts_description = models.TextField(
        default="Stay informed with our latest articles on educational technology, learning methodologies, and industry insights.",
        help_text="Description text for the recent posts section",
    )
    recent_posts_count = models.IntegerField(
        default=3, help_text="Number of recent posts to display"
    )

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("hero_title"),
                FieldPanel("hero_subtitle"),
                FieldPanel("hero_image"),
                FieldPanel("hero_cta_text"),
                FieldPanel("hero_cta_link"),
            ],
            heading="Hero Section",
        ),
        MultiFieldPanel(
            [
                FieldPanel("features_title"),
                FieldPanel("features_description"),
                FieldPanel("features"),
            ],
            heading="Features Section",
        ),
        MultiFieldPanel(
            [
                FieldPanel("testimonials_title"),
                FieldPanel("testimonials_description"),
                FieldPanel("testimonials"),
            ],
            heading="Testimonials",
        ),
        MultiFieldPanel(
            [
                FieldPanel("show_recent_posts"),
                FieldPanel("recent_posts_title"),
                FieldPanel("recent_posts_description"),
                FieldPanel("recent_posts_count"),
            ],
            heading="Recent Posts Section",
        ),
    ]

    def get_recent_posts(self):
        """Get recent blog posts for the homepage"""
        if not self.show_recent_posts:
            return []

        from blog.models import BlogPage

        return BlogPage.objects.live().order_by("-first_published_at")[
            : self.recent_posts_count
        ]

    parent_page_types = []
    subpage_types = [
        "home.AboutPage",
        "home.ContactPage",
        "portfolio.PortfolioIndexPage",
        "blog.BlogIndexPage",
    ]

    class Meta:
        verbose_name = "Home Page"


class AboutPage(Page):
    # Hero Section
    hero_title = models.CharField(
        max_length=255,
        default="About THINK eLearn",
        help_text="Main headline for the about page",
    )
    hero_subtitle = models.TextField(
        blank=True, help_text="Subtitle text below the main headline"
    )
    hero_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Hero background or team image",
    )

    # Company Story
    story_title = models.CharField(
        max_length=255,
        default="Our Story",
        help_text="Title for the company story section",
    )
    story_content = RichTextField(
        blank=True, help_text="Rich text content about the company story"
    )

    # Mission & Values
    mission_title = models.CharField(
        max_length=255, default="Our Mission", help_text="Title for the mission section"
    )
    mission_content = RichTextField(
        blank=True, help_text="Rich text content about the company mission"
    )

    values_title = models.CharField(
        max_length=255, default="Our Values", help_text="Title for the values section"
    )
    values = StreamField(
        [
            (
                "value",
                blocks.StructBlock(
                    [
                        (
                            "icon",
                            blocks.CharBlock(
                                help_text="Font Awesome icon class (e.g., 'fas fa-heart')"
                            ),
                        ),
                        ("title", blocks.CharBlock(max_length=100)),
                        ("description", blocks.TextBlock()),
                    ]
                ),
            )
        ],
        blank=True,
        use_json_field=True,
    )

    # Team Section
    team_title = models.CharField(
        max_length=255, default="Meet Our Team", help_text="Title for the team section"
    )
    team_members = StreamField(
        [
            (
                "member",
                blocks.StructBlock(
                    [
                        ("name", blocks.CharBlock(max_length=100)),
                        ("role", blocks.CharBlock(max_length=100)),
                        ("bio", blocks.TextBlock()),
                        ("photo", ImageChooserBlock(required=False)),
                        (
                            "linkedin",
                            blocks.URLBlock(
                                required=False, help_text="LinkedIn profile URL"
                            ),
                        ),
                        (
                            "twitter",
                            blocks.URLBlock(
                                required=False, help_text="Twitter profile URL"
                            ),
                        ),
                        ("email", blocks.EmailBlock(required=False)),
                    ]
                ),
            )
        ],
        blank=True,
        use_json_field=True,
    )

    # Timeline/Milestones
    timeline_title = models.CharField(
        max_length=255,
        default="Our Journey",
        help_text="Title for the timeline section",
    )
    milestones = StreamField(
        [
            (
                "milestone",
                blocks.StructBlock(
                    [
                        (
                            "year",
                            blocks.CharBlock(
                                max_length=4, help_text="Year (e.g., '2020')"
                            ),
                        ),
                        ("title", blocks.CharBlock(max_length=100)),
                        ("description", blocks.TextBlock()),
                    ]
                ),
            )
        ],
        blank=True,
        use_json_field=True,
    )

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("hero_title"),
                FieldPanel("hero_subtitle"),
                FieldPanel("hero_image"),
            ],
            heading="Hero Section",
        ),
        MultiFieldPanel(
            [
                FieldPanel("story_title"),
                FieldPanel("story_content"),
            ],
            heading="Company Story",
        ),
        MultiFieldPanel(
            [
                FieldPanel("mission_title"),
                FieldPanel("mission_content"),
            ],
            heading="Mission",
        ),
        MultiFieldPanel(
            [
                FieldPanel("values_title"),
                FieldPanel("values"),
            ],
            heading="Values",
        ),
        MultiFieldPanel(
            [
                FieldPanel("team_title"),
                FieldPanel("team_members"),
            ],
            heading="Team",
        ),
        MultiFieldPanel(
            [
                FieldPanel("timeline_title"),
                FieldPanel("milestones"),
            ],
            heading="Timeline/Milestones",
        ),
    ]

    parent_page_types = []
    subpage_types = []

    class Meta:
        verbose_name = "About Page"


class ContactFormField(AbstractFormField):
    page = ParentalKey(
        "ContactPage", on_delete=models.CASCADE, related_name="form_fields"
    )


class ContactPage(AbstractEmailForm):
    # Hero Section
    hero_title = models.CharField(
        max_length=255,
        default="Contact Us",
        help_text="Main headline for the contact page",
    )
    hero_subtitle = models.TextField(
        blank=True, help_text="Subtitle text below the main headline"
    )

    # Introduction
    intro_text = RichTextField(
        blank=True, help_text="Introduction text above the contact form"
    )

    # Contact Information
    show_contact_info = models.BooleanField(
        default=True, help_text="Display contact information section"
    )
    phone = models.CharField(max_length=20, blank=True, help_text="Phone number")
    email = models.EmailField(blank=True, help_text="Contact email address")
    address = models.TextField(blank=True, help_text="Office address")

    # Office Hours
    office_hours = models.TextField(blank=True, help_text="Office hours information")

    # Social Media
    linkedin_url = models.URLField(blank=True, help_text="LinkedIn profile URL")
    twitter_url = models.URLField(blank=True, help_text="Twitter profile URL")
    facebook_url = models.URLField(blank=True, help_text="Facebook page URL")

    # FAQ Section
    show_faq = models.BooleanField(default=True, help_text="Display FAQ section")
    faq_title = models.CharField(
        max_length=255,
        default="Frequently Asked Questions",
        help_text="Title for the FAQ section",
    )
    faqs = StreamField(
        [
            (
                "faq",
                blocks.StructBlock(
                    [
                        ("question", blocks.CharBlock(max_length=200)),
                        ("answer", blocks.TextBlock()),
                    ]
                ),
            )
        ],
        blank=True,
        use_json_field=True,
    )

    # Form Settings
    thank_you_text = RichTextField(
        blank=True, help_text="Thank you message shown after form submission"
    )

    content_panels = AbstractEmailForm.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("hero_title"),
                FieldPanel("hero_subtitle"),
            ],
            heading="Hero Section",
        ),
        FieldPanel("intro_text"),
        MultiFieldPanel(
            [
                FieldPanel("show_contact_info"),
                FieldPanel("phone"),
                FieldPanel("email"),
                FieldPanel("address"),
                FieldPanel("office_hours"),
            ],
            heading="Contact Information",
        ),
        MultiFieldPanel(
            [
                FieldPanel("linkedin_url"),
                FieldPanel("twitter_url"),
                FieldPanel("facebook_url"),
            ],
            heading="Social Media",
        ),
        MultiFieldPanel(
            [
                FieldPanel("show_faq"),
                FieldPanel("faq_title"),
                FieldPanel("faqs"),
            ],
            heading="FAQ Section",
        ),
        FieldPanel("thank_you_text"),
        MultiFieldPanel(
            [
                FieldPanel("to_address"),
                FieldPanel("from_address"),
                FieldPanel("subject"),
            ],
            heading="Email Settings",
        ),
        FormSubmissionsPanel(),
    ]

    parent_page_types = []
    subpage_types = []

    class Meta:
        verbose_name = "Contact Page"


class ProcessPage(Page):
    # Hero Section
    hero_title = models.CharField(
        max_length=255,
        default="THINK eLearn Process",
        help_text="Main headline for the process page",
    )
    hero_subtitle = models.TextField(
        blank=True, help_text="Subtitle text below the main headline"
    )
    hero_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Hero background",
    )

    # Process Sections
    process_sections = StreamField(
        [
            ("process", ProcessBlock()),
        ],
        blank=True,
        help_text="Add multiple process sections as needed",
    )

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("hero_title"),
                FieldPanel("hero_subtitle"),
                FieldPanel("hero_image"),
            ],
            heading="Hero Section",
        ),
        FieldPanel("process_sections"),
    ]

    parent_page_types = []
    subpage_types = []

    class Meta:
        verbose_name = "Process Page"
