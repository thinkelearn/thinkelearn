from django.conf import settings
from django.http import HttpResponse, StreamingHttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from twilio.twiml.voice_response import VoiceResponse
from twilio.twiml.messaging_response import MessagingResponse
from .models import VoicemailMessage, SMSMessage
from .utils import send_voicemail_notification, send_sms_notification
import requests
import logging

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class VoicemailWebhookView(View):
    def post(self, request):
        recording_url = request.POST.get("RecordingUrl")
        recording_sid = request.POST.get("RecordingSid")
        caller_number = request.POST.get("From")
        duration = request.POST.get("RecordingDuration")

        if recording_url and recording_sid:
            voicemail = VoicemailMessage.objects.create(
                recording_url=recording_url,
                recording_sid=recording_sid,
                caller_number=caller_number,
                duration=int(duration) if duration else None,
            )

            # Send email notification
            try:
                send_voicemail_notification(voicemail)
            except Exception as e:
                logger.error(f"Failed to send voicemail notification: {e}")

        response = VoiceResponse()
        response.say("Thank you for your message. We'll get back to you soon. Goodbye!")
        response.hangup()

        return HttpResponse(str(response), content_type="text/xml")


@method_decorator(csrf_exempt, name="dispatch")
class SMSWebhookView(View):
    def post(self, request):
        message_sid = request.POST.get("MessageSid")
        from_number = request.POST.get("From")
        to_number = request.POST.get("To")
        body = request.POST.get("Body", "")
        media_url = request.POST.get("MediaUrl0", "")

        if message_sid:
            sms = SMSMessage.objects.create(
                message_sid=message_sid,
                from_number=from_number,
                to_number=to_number,
                body=body,
                media_url=media_url,
            )

            # Send email notification
            try:
                send_sms_notification(sms)
            except Exception as e:
                logger.error(f"Failed to send SMS notification: {e}")

        response = MessagingResponse()
        response.message("Thank you for your message! We'll get back to you soon.")

        return HttpResponse(str(response), content_type="text/xml")


@login_required
def recording_proxy_view(request, voicemail_id):
    """Proxy voicemail recordings from Twilio with authentication."""
    voicemail = get_object_or_404(VoicemailMessage, id=voicemail_id)

    if not voicemail.recording_url:
        raise Http404("Recording not available")

    try:
        # Get recording URL from Twilio
        recording_url = voicemail.recording_url

        # Fetch the recording from Twilio with authentication
        response = requests.get(
            recording_url,
            stream=True,
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
        )
        response.raise_for_status()

        # Create streaming response
        def generate():
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk

        # Return streaming response with appropriate headers
        streaming_response = StreamingHttpResponse(
            generate(), content_type=response.headers.get("content-type", "audio/wav")
        )
        streaming_response["Content-Disposition"] = (
            f'inline; filename="voicemail_{voicemail.id}.wav"'
        )
        streaming_response["Content-Length"] = response.headers.get(
            "content-length", ""
        )

        return streaming_response

    except Exception as e:
        logger.error(f"Error streaming recording {voicemail_id}: {e}")
        raise Http404("Recording could not be loaded")


@login_required
def recording_player_view(request, voicemail_id):
    """Display audio player for voicemail recording."""
    voicemail = get_object_or_404(VoicemailMessage, id=voicemail_id)

    if not voicemail.recording_url:
        raise Http404("Recording not available")

    context = {
        "voicemail": voicemail,
        "recording_stream_url": f"/communications/recording/{voicemail_id}/",
    }

    return TemplateResponse(request, "communications/recording_player.html", context)
