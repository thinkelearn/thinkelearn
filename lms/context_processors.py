"""LMS context processors."""

from lms.models import ClientDemoInvite


def active_demo(request):
    """
    Injects ``demo_return_url`` into every template context when the current
    session has a valid, active demo invite.

    Set by ``client_demo_view`` when a client lands via a demo link.
    Consumed by course/lesson templates to render the demo mode bar.
    """
    token = request.session.get("active_demo_token")
    if not token:
        return {}

    try:
        invite = ClientDemoInvite.objects.get(token=token)
        if invite.is_valid():
            return {"demo_return_url": invite.get_absolute_url()}
        # Invite has expired or been deactivated — clean up the session key
        del request.session["active_demo_token"]
    except (ClientDemoInvite.DoesNotExist, ValueError):
        request.session.pop("active_demo_token", None)

    return {}
