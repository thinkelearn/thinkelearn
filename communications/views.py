from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from twilio.twiml.voice_response import VoiceResponse
from twilio.twiml.messaging_response import MessagingResponse
from .models import VoicemailMessage, SMSMessage


@method_decorator(csrf_exempt, name="dispatch")
class VoicemailWebhookView(View):
    def post(self, request):
        recording_url = request.POST.get("RecordingUrl")
        recording_sid = request.POST.get("RecordingSid")
        caller_number = request.POST.get("From")
        duration = request.POST.get("RecordingDuration")

        if recording_url and recording_sid:
            VoicemailMessage.objects.create(
                recording_url=recording_url,
                recording_sid=recording_sid,
                caller_number=caller_number,
                duration=int(duration) if duration else None,
            )

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
            SMSMessage.objects.create(
                message_sid=message_sid,
                from_number=from_number,
                to_number=to_number,
                body=body,
                media_url=media_url,
            )

        response = MessagingResponse()
        response.message("Thank you for your message! We'll get back to you soon.")

        return HttpResponse(str(response), content_type="text/xml")
