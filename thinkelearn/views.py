from django.shortcuts import render


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
