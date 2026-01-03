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


def parent_help(request):
    """Render the parent help page."""
    return render(
        request,
        "parent_help.html",
        {
            "page_title": "Parent Help",
            "meta_description": "Guidance for parents using Google Family Link or Microsoft Family Safety with THINK eLearn.",
        },
    )
