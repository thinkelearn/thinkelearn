# Wagtail Page Models Specification

## Core Page Models

### 1. HomePage (Enhanced)

```python
class HomePage(Page):
    # Hero Section
    hero_title = models.CharField(max_length=255, default="Empowering Learning Through Innovation")
    hero_subtitle = models.TextField(blank=True)
    hero_image = models.ForeignKey('wagtailimages.Image', null=True, blank=True, on_delete=models.SET_NULL)
    hero_cta_text = models.CharField(max_length=50, default="Get Started")
    hero_cta_link = models.ForeignKey('wagtailcore.Page', null=True, blank=True, on_delete=models.SET_NULL)

    # Features Section
    features_title = models.CharField(max_length=255, default="Why Choose THINK eLearn")
    features = StreamField([
        ('feature', blocks.StructBlock([
            ('icon', blocks.CharBlock(help_text="Font Awesome icon class")),
            ('title', blocks.CharBlock()),
            ('description', blocks.TextBlock()),
        ]))
    ], blank=True)

    # Testimonials
    testimonials = StreamField([
        ('testimonial', blocks.StructBlock([
            ('quote', blocks.TextBlock()),
            ('author', blocks.CharBlock()),
            ('company', blocks.CharBlock(required=False)),
            ('avatar', ImageChooserBlock(required=False)),
        ]))
    ], blank=True)

    # Recent Blog Posts (auto-populated)
    show_recent_posts = models.BooleanField(default=True)
    recent_posts_count = models.IntegerField(default=3)
```

### 2. AboutPage

```python
class AboutPage(Page):
    # Company Story
    story_title = models.CharField(max_length=255, default="Our Story")
    story_content = RichTextField()
    story_image = models.ForeignKey('wagtailimages.Image', null=True, blank=True, on_delete=models.SET_NULL)

    # Mission & Values
    mission_title = models.CharField(max_length=255, default="Our Mission")
    mission_content = RichTextField()

    values = StreamField([
        ('value', blocks.StructBlock([
            ('title', blocks.CharBlock()),
            ('description', blocks.TextBlock()),
            ('icon', blocks.CharBlock(help_text="Font Awesome icon class")),
        ]))
    ], blank=True)

    # Team Section
    team_title = models.CharField(max_length=255, default="Meet Our Team")
    team_members = StreamField([
        ('member', blocks.StructBlock([
            ('name', blocks.CharBlock()),
            ('position', blocks.CharBlock()),
            ('bio', blocks.TextBlock()),
            ('photo', ImageChooserBlock()),
            ('linkedin', blocks.URLBlock(required=False)),
            ('twitter', blocks.URLBlock(required=False)),
        ]))
    ], blank=True)
```

### 3. Blog Models

```python
class BlogIndexPage(Page):
    intro = RichTextField(blank=True)
    featured_post = models.ForeignKey('BlogPage', null=True, blank=True, on_delete=models.SET_NULL)

    def get_blog_posts(self):
        return BlogPage.objects.live().descendant_of(self).order_by('-first_published_at')

class BlogPage(Page):
    # Meta
    author = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    published_date = models.DateTimeField(auto_now_add=True)
    featured_image = models.ForeignKey('wagtailimages.Image', null=True, blank=True, on_delete=models.SET_NULL)
    excerpt = models.TextField(max_length=300, help_text="Brief description for listings")

    # Content
    body = StreamField([
        ('heading', blocks.CharBlock(form_classname="title")),
        ('paragraph', blocks.RichTextBlock()),
        ('image', ImageChooserBlock()),
        ('quote', blocks.BlockQuoteBlock()),
        ('code', blocks.TextBlock(form_classname="monospace")),
        ('embed', EmbedBlock()),
    ])

    # SEO & Organization
    categories = ParentalManyToManyField('BlogCategory', blank=True)
    tags = ClusterTaggableManager(through='BlogPageTag', blank=True)

    # Reading time calculation
    @property
    def reading_time(self):
        word_count = len(self.body.render_as_block().split())
        return max(1, word_count // 200)  # Assume 200 words per minute
```

### 4. Portfolio Models

```python
class PortfolioIndexPage(Page):
    intro = RichTextField(blank=True)
    featured_project = models.ForeignKey('ProjectPage', null=True, blank=True, on_delete=models.SET_NULL)

class ProjectPage(Page):
    # Project Details
    client = models.CharField(max_length=255)
    project_type = models.CharField(max_length=100, choices=[
        ('web', 'Web Development'),
        ('mobile', 'Mobile App'),
        ('elearning', 'E-Learning Platform'),
        ('consulting', 'Consulting'),
    ])
    completion_date = models.DateField()
    project_url = models.URLField(blank=True)

    # Content
    featured_image = models.ForeignKey('wagtailimages.Image', on_delete=models.CASCADE)
    overview = RichTextField()
    challenge = RichTextField(blank=True)
    solution = RichTextField(blank=True)
    results = RichTextField(blank=True)

    # Gallery
    gallery_images = StreamField([
        ('image', ImageChooserBlock()),
    ], blank=True)

    # Technologies Used
    technologies = StreamField([
        ('tech', blocks.StructBlock([
            ('name', blocks.CharBlock()),
            ('category', blocks.ChoiceBlock(choices=[
                ('frontend', 'Frontend'),
                ('backend', 'Backend'),
                ('database', 'Database'),
                ('tools', 'Tools'),
            ])),
        ]))
    ], blank=True)

    # Testimonial
    testimonial_quote = models.TextField(blank=True)
    testimonial_author = models.CharField(max_length=255, blank=True)
    testimonial_position = models.CharField(max_length=255, blank=True)
```

### 5. ContactPage

```python
class ContactPage(Page):
    # Page Content
    intro = RichTextField(blank=True)

    # Contact Information
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = RichTextField(blank=True)

    # Office Locations
    locations = StreamField([
        ('location', blocks.StructBlock([
            ('name', blocks.CharBlock()),
            ('address', blocks.TextBlock()),
            ('phone', blocks.CharBlock(required=False)),
            ('email', blocks.EmailBlock(required=False)),
            ('map_embed', blocks.RawHTMLBlock(required=False)),
        ]))
    ], blank=True)

    # Social Media
    social_links = StreamField([
        ('social', blocks.StructBlock([
            ('platform', blocks.ChoiceBlock(choices=[
                ('linkedin', 'LinkedIn'),
                ('twitter', 'Twitter'),
                ('facebook', 'Facebook'),
                ('instagram', 'Instagram'),
                ('youtube', 'YouTube'),
            ])),
            ('url', blocks.URLBlock()),
        ]))
    ], blank=True)

    # FAQ Section
    faqs = StreamField([
        ('faq', blocks.StructBlock([
            ('question', blocks.CharBlock()),
            ('answer', blocks.RichTextBlock()),
        ]))
    ], blank=True)

# Contact Form (separate model for form submissions)
class ContactFormSubmission(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    company = models.CharField(max_length=255, blank=True)
    subject = models.CharField(max_length=255)
    message = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']
```

### 6. ServicePage (Future)

```python
class ServiceIndexPage(Page):
    intro = RichTextField(blank=True)

class ServicePage(Page):
    # Service Details
    service_type = models.CharField(max_length=100, choices=[
        ('training', 'Training & Workshops'),
        ('consulting', 'Consulting'),
        ('development', 'Custom Development'),
        ('support', 'Support & Maintenance'),
    ])

    # Content
    featured_image = models.ForeignKey('wagtailimages.Image', on_delete=models.CASCADE)
    overview = RichTextField()

    # Features & Benefits
    features = StreamField([
        ('feature', blocks.StructBlock([
            ('title', blocks.CharBlock()),
            ('description', blocks.TextBlock()),
            ('icon', blocks.CharBlock()),
        ]))
    ], blank=True)

    # Pricing (optional)
    show_pricing = models.BooleanField(default=False)
    price_from = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    pricing_note = models.TextField(blank=True)
```

## Supporting Models

### Snippets

```python
# For reusable content blocks
class Testimonial(models.Model):
    quote = models.TextField()
    author = models.CharField(max_length=255)
    company = models.CharField(max_length=255, blank=True)
    avatar = models.ForeignKey('wagtailimages.Image', null=True, blank=True, on_delete=models.SET_NULL)

    panels = [
        FieldPanel('quote'),
        FieldPanel('author'),
        FieldPanel('company'),
        FieldPanel('avatar'),
    ]

class Partner(models.Model):
    name = models.CharField(max_length=255)
    logo = models.ForeignKey('wagtailimages.Image', on_delete=models.CASCADE)
    website = models.URLField(blank=True)

class BlogCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
```

## Implementation Notes

1. **StreamFields**: Used for flexible, structured content
2. **SEO**: All page models include SEO fields via inheritance
3. **Images**: Proper image handling with alt text and responsive sizing
4. **Performance**: QuerySet optimization for listings and related content
5. **Search**: Wagtail's built-in search functionality for blog and projects
6. **Caching**: Template fragment caching for expensive queries
7. **Admin**: Custom admin panels for better content management experience
