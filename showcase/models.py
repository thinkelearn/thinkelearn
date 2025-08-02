from django import forms
from django.db import models
from django.urls import reverse
from modelcluster.fields import ParentalManyToManyField
from wagtail import blocks
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.embeds.blocks import EmbedBlock
from wagtail.fields import RichTextField, StreamField
from wagtail.images.blocks import ImageChooserBlock
from wagtail.models import Page
from wagtail.search import index
from wagtail.snippets.models import register_snippet


class PackagedContentBlock(blocks.StructBlock):
    title = blocks.CharBlock(max_length=100, help_text="Title for this content package")
    description = blocks.TextBlock(
        required=False, help_text="Brief description of the content"
    )
    package_file = DocumentChooserBlock(
        help_text="ZIP file containing the learning module"
    )
    thumbnail = ImageChooserBlock(
        required=False, help_text="Preview image for the content"
    )

    class Meta:
        icon = "doc-full"
        label = "Packaged Learning Module"

    def clean(self, value):
        result = super().clean(value)
        package_file = value.get("package_file")

        if package_file and not package_file.file.name.lower().endswith(".zip"):
            raise blocks.StructBlockValidationError(
                block_errors={
                    "package_file": [
                        "Please upload a ZIP file containing the learning module."
                    ]
                }
            )

        return result


class VideoContentBlock(blocks.StructBlock):
    title = blocks.CharBlock(max_length=100, help_text="Title for this video")
    description = blocks.TextBlock(
        required=False, help_text="Brief description of the video"
    )
    video_type = blocks.ChoiceBlock(
        choices=[
            ("embed", "YouTube/Vimeo Embed"),
            ("upload", "Uploaded Video File"),
        ],
        default="embed",
    )
    embed_url = EmbedBlock(required=False, help_text="YouTube or Vimeo URL")
    video_file = DocumentChooserBlock(required=False, help_text="Uploaded video file")
    thumbnail = ImageChooserBlock(required=False, help_text="Custom thumbnail image")

    class Meta:
        icon = "media"
        label = "Video Content"

    def clean(self, value):
        result = super().clean(value)
        video_type = value.get("video_type")
        video_file = value.get("video_file")
        embed_url = value.get("embed_url")

        if video_type == "embed" and not embed_url:
            raise blocks.StructBlockValidationError(
                block_errors={
                    "embed_url": ["This field is required when using embed type."]
                }
            )

        if video_type == "upload" and not video_file:
            raise blocks.StructBlockValidationError(
                block_errors={
                    "video_file": ["This field is required when using upload type."]
                }
            )

        return result


class GalleryContentBlock(blocks.StructBlock):
    title = blocks.CharBlock(max_length=100, help_text="Title for this gallery")
    description = blocks.TextBlock(
        required=False, help_text="Brief description of the gallery"
    )
    images = blocks.ListBlock(
        blocks.StructBlock(
            [
                ("image", ImageChooserBlock()),
                ("caption", blocks.CharBlock(max_length=200, required=False)),
            ]
        )
    )

    class Meta:
        icon = "image"
        label = "Image Gallery"


class InteractiveContentBlock(blocks.StructBlock):
    title = blocks.CharBlock(max_length=100, help_text="Title for this content")
    description = blocks.TextBlock(
        required=False, help_text="Brief description of the content"
    )
    content_file = DocumentChooserBlock(
        help_text="Interactive content file (animation, PDF, etc.)"
    )
    display_type = blocks.ChoiceBlock(
        choices=[
            ("download", "Download Link Only"),
            ("embed", "Embed/Display Inline"),
            ("iframe", "Display in Frame"),
        ],
        default="download",
    )
    thumbnail = ImageChooserBlock(required=False, help_text="Preview image")

    class Meta:
        icon = "cogs"
        label = "Interactive Content"


@register_snippet
class ShowcaseCategory(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=80)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Font Awesome icon class (e.g., 'fas fa-graduation-cap')",
    )

    panels = [
        FieldPanel("name"),
        FieldPanel("slug"),
        FieldPanel("description"),
        FieldPanel("icon"),
    ]

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Showcase Categories"


class ShowcaseIndexPage(Page):
    intro = RichTextField(
        blank=True, help_text="Introduction text for the showcase section"
    )

    # Hero Section
    hero_title = models.CharField(
        max_length=255,
        default="Our Work Showcase",
        help_text="Main headline for the showcase page",
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
        help_text="Hero background image",
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
        FieldPanel("intro"),
    ]

    parent_page_types = []
    subpage_types = ["showcase.ShowcasePage"]

    def get_context(self, request):
        context = super().get_context(request)
        showcases = self.get_children().live().order_by("-first_published_at")

        # Filter by category if provided
        category = request.GET.get("category")
        if category:
            showcases = showcases.filter(showcasepage__categories__slug=category)

        context["showcases"] = showcases
        context["categories"] = ShowcaseCategory.objects.all()
        return context

    class Meta:
        verbose_name = "Showcase Index Page"


class ShowcasePage(Page):
    # Basic Info
    showcase_date = models.DateField("Creation date", null=True, blank=True)
    intro = models.CharField(max_length=250, help_text="Brief introduction/summary")
    description = RichTextField(blank=True, help_text="Detailed description")

    # Featured Image
    featured_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Main featured image for this showcase",
    )

    # Categories and Tags
    categories = ParentalManyToManyField("showcase.ShowcaseCategory", blank=True)
    technologies = models.TextField(
        blank=True, help_text="Comma-separated list of technologies/tools used"
    )

    # Content Sections
    content_sections = StreamField(
        [
            ("packaged_content", PackagedContentBlock()),
            ("video_content", VideoContentBlock()),
            ("gallery_content", GalleryContentBlock()),
            ("interactive_content", InteractiveContentBlock()),
            (
                "text_content",
                blocks.StructBlock(
                    [
                        ("title", blocks.CharBlock(max_length=100, required=False)),
                        ("content", blocks.RichTextBlock()),
                    ],
                    icon="doc-full",
                    label="Text Content",
                ),
            ),
        ],
        blank=True,
        use_json_field=True,
        help_text="Add different types of content to showcase your work",
    )

    # Metadata
    target_audience = models.TextField(
        blank=True, help_text="Who is this content designed for?"
    )
    learning_objectives = models.TextField(
        blank=True, help_text="What will users learn or achieve?"
    )
    duration = models.CharField(
        max_length=50,
        blank=True,
        help_text="Estimated time to complete (e.g., '15 minutes', '2 hours')",
    )

    search_fields = Page.search_fields + [
        index.SearchField("intro"),
        index.SearchField("description"),
        index.SearchField("technologies"),
        index.SearchField("target_audience"),
    ]

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("showcase_date"),
                FieldPanel("categories", widget=forms.CheckboxSelectMultiple),
                FieldPanel("technologies"),
            ],
            heading="Basic Information",
        ),
        FieldPanel("intro"),
        FieldPanel("description"),
        FieldPanel("featured_image"),
        FieldPanel("content_sections"),
        MultiFieldPanel(
            [
                FieldPanel("target_audience"),
                FieldPanel("learning_objectives"),
                FieldPanel("duration"),
            ],
            heading="Learning Metadata",
        ),
    ]

    parent_page_types = ["showcase.ShowcaseIndexPage"]
    subpage_types = []

    def get_technologies_list(self):
        """Return technologies as a list"""
        if self.technologies:
            return [tech.strip() for tech in self.technologies.split(",")]
        return []

    def get_packaged_content_url(self, document):
        """Generate URL for packaged content viewer"""
        return reverse("showcase:package_viewer", args=[self.pk, document.pk])

    def get_context(self, request):
        context = super().get_context(request)

        # Get related showcases (same categories)
        related_showcases = ShowcasePage.objects.live().exclude(id=self.id)
        if self.categories.exists():
            related_showcases = related_showcases.filter(
                categories__in=self.categories.all()
            ).distinct()

        context["related_showcases"] = related_showcases[:3]
        return context

    class Meta:
        verbose_name = "Showcase Page"
