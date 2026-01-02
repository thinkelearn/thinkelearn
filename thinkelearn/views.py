from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET", "POST"])
def signup_closed(request):
    """Return 403 Forbidden when registration is disabled."""
    return HttpResponse(
        "<h1>Registration Closed</h1>"
        "<p>We're not accepting new registrations at this time. Please check back later.</p>",
        status=403,
        content_type="text/html",
    )


def privacy_policy(request):
    """Render the privacy policy page."""
    return render(
        request,
        "privacy.html",
        {
            "page_title": "Privacy Policy",
            "meta_description": "Read our privacy policy to understand how THINK eLearn collects, uses, and protects your personal information.",
        },
    )


def terms_and_conditions(request):
    """Render the terms and conditions page."""
    return render(
        request,
        "terms.html",
        {
            "page_title": "Terms and Conditions",
            "meta_description": "Read our terms and conditions to understand the legal agreement governing your use of THINK eLearn services.",
        },
    )
