from django import forms
from django.db import models
from modelcluster.fields import ParentalManyToManyField
from wagtail import blocks
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page
from wagtail.search import index
from wagtail.snippets.models import register_snippet


class PortfolioIndexPage(Page):
    intro = RichTextField(blank=True)

    content_panels = Page.content_panels + [FieldPanel("intro")]

    parent_page_types = []
    subpage_types = ["portfolio.ProjectPage"]

    def get_context(self, request):
        # Update context to include only published projects, ordered by reverse-chron
        context = super().get_context(request)
        projects = self.get_children().live().order_by("-first_published_at")

        # Filter by category if provided
        category = request.GET.get("category")
        if category:
            projects = projects.filter(projectpage__categories__slug=category)

        context["projects"] = projects
        context["categories"] = ProjectCategory.objects.all()
        return context


@register_snippet
class ProjectCategory(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=80)
    description = models.TextField(blank=True)

    panels = [
        FieldPanel("name"),
        FieldPanel("slug"),
        FieldPanel("description"),
    ]

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Project Categories"


class ProjectPage(Page):
    # Basic Info
    project_date = models.DateField("Project completion date")
    client_name = models.CharField(max_length=200, blank=True)
    project_url = models.URLField(blank=True, help_text="Live project URL")
    intro = models.CharField(max_length=250)
    description = RichTextField(blank=True)

    # Images
    featured_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    # Project Details
    categories = ParentalManyToManyField("portfolio.ProjectCategory", blank=True)
    technologies = models.TextField(
        blank=True, help_text="Comma-separated list of technologies used"
    )

    # Results & Metrics
    results_title = models.CharField(
        max_length=255,
        default="Results & Impact",
        help_text="Title for the results section",
    )
    results = StreamField(
        [
            (
                "metric",
                blocks.StructBlock(
                    [
                        ("label", blocks.CharBlock(max_length=100)),
                        ("value", blocks.CharBlock(max_length=50)),
                        ("description", blocks.TextBlock(required=False)),
                    ]
                ),
            )
        ],
        blank=True,
        use_json_field=True,
    )

    # Case Study Sections
    challenge_title = models.CharField(
        max_length=255,
        default="The Challenge",
        help_text="Title for the challenge section",
    )
    challenge_content = RichTextField(blank=True)

    solution_title = models.CharField(
        max_length=255,
        default="Our Solution",
        help_text="Title for the solution section",
    )
    solution_content = RichTextField(blank=True)

    # Testimonial
    testimonial_quote = models.TextField(blank=True)
    testimonial_author = models.CharField(max_length=100, blank=True)
    testimonial_company = models.CharField(max_length=100, blank=True)
    testimonial_avatar = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    search_fields = Page.search_fields + [
        index.SearchField("intro"),
        index.SearchField("description"),
        index.SearchField("client_name"),
    ]

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("project_date"),
                FieldPanel("client_name"),
                FieldPanel("project_url"),
                FieldPanel("categories", widget=forms.CheckboxSelectMultiple),
                FieldPanel("technologies"),
            ],
            heading="Project Information",
        ),
        FieldPanel("intro"),
        FieldPanel("description"),
        FieldPanel("featured_image"),
        MultiFieldPanel(
            [
                FieldPanel("challenge_title"),
                FieldPanel("challenge_content"),
            ],
            heading="Challenge",
        ),
        MultiFieldPanel(
            [
                FieldPanel("solution_title"),
                FieldPanel("solution_content"),
            ],
            heading="Solution",
        ),
        MultiFieldPanel(
            [
                FieldPanel("results_title"),
                FieldPanel("results"),
            ],
            heading="Results & Metrics",
        ),
        MultiFieldPanel(
            [
                FieldPanel("testimonial_quote"),
                FieldPanel("testimonial_author"),
                FieldPanel("testimonial_company"),
                FieldPanel("testimonial_avatar"),
            ],
            heading="Client Testimonial",
        ),
    ]

    parent_page_types = ["portfolio.PortfolioIndexPage"]
    subpage_types = []

    def get_technologies_list(self):
        """Return technologies as a list"""
        if self.technologies:
            return [tech.strip() for tech in self.technologies.split(",")]
        return []

    def get_context(self, request):
        context = super().get_context(request)

        # Get related projects (same categories)
        related_projects = ProjectPage.objects.live().exclude(id=self.id)
        if self.categories.exists():
            related_projects = related_projects.filter(
                categories__in=self.categories.all()
            )

        context["related_projects"] = related_projects.distinct()[:3]
        return context
