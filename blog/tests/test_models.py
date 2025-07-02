import factory
from django.http import HttpRequest
from django.test import TestCase
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase
from wagtail_factories import ImageFactory, PageFactory

from blog.models import BlogCategory, BlogIndexPage, BlogPage, BlogPageTag


class BlogCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BlogCategory

    name = factory.Sequence(lambda n: f"Category {n}")
    slug = factory.Sequence(lambda n: f"category-{n}")
    description = "Test blog category description"


class BlogIndexPageFactory(PageFactory):
    class Meta:
        model = BlogIndexPage

    title = "Blog"
    intro = "<p>Welcome to our blog</p>"


class BlogPageFactory(PageFactory):
    class Meta:
        model = BlogPage

    title = factory.Sequence(lambda n: f"Blog Post {n}")
    date = factory.Faker("date_this_year")
    intro = factory.Faker("sentence", nb_words=20)
    body = factory.Faker("text")
    author_name = "Test Author"


class BlogCategoryTest(TestCase):
    def test_can_create_category(self):
        category = BlogCategoryFactory()
        self.assertIsInstance(category, BlogCategory)
        self.assertTrue(category.name.startswith("Category"))
        self.assertTrue(category.slug.startswith("category-"))

    def test_category_str_method(self):
        category = BlogCategoryFactory(name="Technology")
        self.assertEqual(str(category), "Technology")

    def test_category_slug_unique(self):
        BlogCategoryFactory(slug="unique-slug")
        with self.assertRaises((ValueError, Exception)):
            BlogCategoryFactory(slug="unique-slug")

    def test_category_verbose_name_plural(self):
        self.assertEqual(BlogCategory._meta.verbose_name_plural, "Blog Categories")


class BlogIndexPageTest(WagtailPageTestCase):
    def setUp(self):
        self.root_page = Page.objects.get(id=2)

    def test_can_create_blog_index(self):
        blog_index = BlogIndexPageFactory(parent=self.root_page)
        self.assertIsInstance(blog_index, BlogIndexPage)
        self.assertEqual(blog_index.title, "Blog")

    def test_blog_index_subpage_types(self):
        self.assertEqual(BlogIndexPage.subpage_types, ["blog.BlogPage"])

    def test_blog_index_parent_page_types(self):
        self.assertEqual(BlogIndexPage.parent_page_types, [])

    def test_get_context_with_no_posts(self):
        blog_index = BlogIndexPageFactory(parent=self.root_page)
        request = HttpRequest()
        context = blog_index.get_context(request)

        self.assertIn("posts", context)
        self.assertIn("categories", context)
        self.assertEqual(len(context["posts"]), 0)

    def test_get_context_with_posts(self):
        blog_index = BlogIndexPageFactory(parent=self.root_page)

        # Create some blog posts
        for _ in range(3):
            BlogPageFactory(parent=blog_index)

        request = HttpRequest()
        context = blog_index.get_context(request)

        self.assertIn("posts", context)
        self.assertEqual(len(context["posts"]), 3)

    def test_pagination(self):
        blog_index = BlogIndexPageFactory(parent=self.root_page)

        # Create more posts than the pagination limit (6)
        for _ in range(8):
            BlogPageFactory(parent=blog_index)

        request = HttpRequest()
        context = blog_index.get_context(request)

        posts = context["posts"]
        self.assertEqual(len(posts), 6)  # Should be paginated to 6 per page
        self.assertTrue(posts.has_next())

    def test_category_filtering(self):
        blog_index = BlogIndexPageFactory(parent=self.root_page)
        category = BlogCategoryFactory(slug="tech")

        # Create posts with and without category
        post_with_category = BlogPageFactory(parent=blog_index)
        post_with_category.categories.add(category)

        BlogPageFactory(parent=blog_index)  # post_without_category

        # Test filtering by category
        request = HttpRequest()
        request.GET = {"category": "tech"}
        context = blog_index.get_context(request)

        posts = context["posts"]
        self.assertEqual(len(posts), 1)


class BlogPageTest(WagtailPageTestCase):
    def setUp(self):
        self.root_page = Page.objects.get(id=2)
        self.blog_index = BlogIndexPageFactory(parent=self.root_page)

    def test_can_create_blog_page(self):
        blog_page = BlogPageFactory(parent=self.blog_index)
        self.assertIsInstance(blog_page, BlogPage)
        self.assertTrue(blog_page.title.startswith("Blog Post"))

    def test_blog_page_constraints(self):
        self.assertEqual(BlogPage.parent_page_types, ["blog.BlogIndexPage"])
        self.assertEqual(BlogPage.subpage_types, [])

    def test_blog_page_defaults(self):
        blog_page = BlogPage(title="Test Post")
        self.assertEqual(blog_page.author_name, "THINK eLearn Team")

    def test_blog_page_search_fields(self):
        search_fields = [field.field_name for field in BlogPage.search_fields]
        self.assertIn("intro", search_fields)
        self.assertIn("body", search_fields)

    def test_main_image_with_featured_image(self):
        image = ImageFactory()
        blog_page = BlogPageFactory(parent=self.blog_index, featured_image=image)
        self.assertEqual(blog_page.main_image(), image)

    def test_main_image_without_featured_image(self):
        blog_page = BlogPageFactory(parent=self.blog_index)
        self.assertIsNone(blog_page.main_image())

    def test_get_context_related_posts_by_category(self):
        category = BlogCategoryFactory()

        # Create main post with category
        main_post = BlogPageFactory(parent=self.blog_index)
        main_post.categories.add(category)

        # Create related post with same category
        related_post = BlogPageFactory(parent=self.blog_index)
        related_post.categories.add(category)

        # Create unrelated post
        unrelated_post = BlogPageFactory(parent=self.blog_index)

        request = HttpRequest()
        context = main_post.get_context(request)

        self.assertIn("related_posts", context)
        related_posts = context["related_posts"]
        self.assertIn(related_post, related_posts)
        self.assertNotIn(unrelated_post, related_posts)
        self.assertNotIn(main_post, related_posts)  # Should exclude itself

    def test_get_context_related_posts_by_tags(self):
        # Create main post without categories but with tags
        main_post = BlogPageFactory(parent=self.blog_index)
        main_post.tags.add("python", "django")

        # Create related post with same tag
        related_post = BlogPageFactory(parent=self.blog_index)
        related_post.tags.add("python")

        # Create unrelated post
        unrelated_post = BlogPageFactory(parent=self.blog_index)
        unrelated_post.tags.add("javascript")

        request = HttpRequest()
        context = main_post.get_context(request)

        self.assertIn("related_posts", context)
        related_posts = context["related_posts"]
        self.assertIn(related_post, related_posts)
        self.assertNotIn(unrelated_post, related_posts)

    def test_get_context_no_related_posts(self):
        blog_page = BlogPageFactory(parent=self.blog_index)

        request = HttpRequest()
        context = blog_page.get_context(request)

        self.assertIn("related_posts", context)
        self.assertEqual(len(context["related_posts"]), 0)

    def test_blog_page_tag_relationship(self):
        blog_page = BlogPageFactory(parent=self.blog_index)
        blog_page.tags.add("test-tag", "another-tag")

        self.assertEqual(blog_page.tags.count(), 2)
        self.assertIn("test-tag", [tag.name for tag in blog_page.tags.all()])

    def test_blog_page_category_relationship(self):
        category1 = BlogCategoryFactory()
        category2 = BlogCategoryFactory()

        blog_page = BlogPageFactory(parent=self.blog_index)
        blog_page.categories.add(category1, category2)

        self.assertEqual(blog_page.categories.count(), 2)
        self.assertIn(category1, blog_page.categories.all())
        self.assertIn(category2, blog_page.categories.all())


class BlogPageTagTest(TestCase):
    def test_blog_page_tag_model(self):
        """Test that BlogPageTag model exists and works correctly"""
        self.assertTrue(hasattr(BlogPageTag, "content_object"))
        self.assertEqual(BlogPageTag.content_object.field.related_model, BlogPage)
