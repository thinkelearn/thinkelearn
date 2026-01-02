import time

from django.test import TestCase
from wagtail.models import Page

from home.models import ContactFormField, ContactPage


class ContactFormSpamProtectionTest(TestCase):
    def setUp(self):
        self.root_page = Page.add_root(title="Root")
        self.contact_page = ContactPage(title="Contact", slug="contact")
        self.root_page.add_child(instance=self.contact_page)

        ContactFormField.objects.create(
            page=self.contact_page,
            sort_order=1,
            label="Name",
            field_type="singleline",
            required=True,
        )
        ContactFormField.objects.create(
            page=self.contact_page,
            sort_order=2,
            label="Email",
            field_type="email",
            required=True,
        )
        ContactFormField.objects.create(
            page=self.contact_page,
            sort_order=3,
            label="Subject",
            field_type="singleline",
            required=True,
        )
        ContactFormField.objects.create(
            page=self.contact_page,
            sort_order=4,
            label="Message",
            field_type="multiline",
            required=True,
        )

    def _build_form(self, **overrides):
        form_class = self.contact_page.get_form_class()
        form_data = {
            "name": "Tester",
            "email": "tester@example.com",
            "subject": "Hello",
            "message": "I have a question about your services.",
            "website": "",
            "timestamp": str(time.time() - 5),
        }
        form_data.update(overrides)
        return form_class(data=form_data)

    def test_valid_submission_is_accepted(self):
        form = self._build_form()
        self.assertTrue(form.is_valid())

    def test_honeypot_submission_is_rejected(self):
        form = self._build_form(website="bot payload")
        self.assertFalse(form.is_valid())
        self.assertIn("Invalid submission.", form.errors["website"])

    def test_fast_submission_is_rejected(self):
        form = self._build_form(timestamp=str(time.time()))
        self.assertFalse(form.is_valid())
        self.assertIn(
            "Please wait a moment before submitting the form.",
            form.non_field_errors(),
        )

    def test_link_heavy_message_is_rejected(self):
        message = "Check http://a.com and https://b.com and http://c.com"
        form = self._build_form(message=message)
        self.assertFalse(form.is_valid())
        self.assertIn(
            "Please remove links from your message so we can process it.",
            form.non_field_errors(),
        )
