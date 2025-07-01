# Twilio Integration Documentation

## Overview

THINK eLearn integrates with Twilio to handle voice calls and SMS messages through Django webhooks. This setup provides voicemail recording and SMS message handling capabilities.

## Architecture

- **Django App**: `communications` - Handles Twilio webhooks and stores messages
- **Database Models**: `VoicemailMessage` and `SMSMessage` for storing communications
- **Webhooks**: Django endpoints that receive Twilio webhook data
- **Admin Interface**: Django admin panels for viewing messages

## Setup Instructions

### 1. Twilio Account Setup

1. **Purchase a Twilio Phone Number**
   - Log into your Twilio Console
   - Navigate to Phone Numbers → Manage → Buy a number
   - Choose a number that supports Voice and SMS

2. **Create TwiML Bin for Voice**
   - Navigate to Runtime → TwiML Bins
   - Create a new TwiML Bin with the following content:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Dial timeout="10">+14169093199</Dial>
  <Say>Thank you for calling THINK eLearn.</Say>
  <Say>We're currently unavailable. Please leave your message after the beep, and we'll get back to you as soon as we can.</Say>
  <Record maxLength="60" action="https://web-production-17c5.up.railway.app/communications/handle-recording" />
  <Say>We didn't receive a message. Goodbye!</Say>
</Response>
```

### 2. Environment Variables

Set the following environment variables in your deployment platform (Railway):

```bash
TWILIO_ACCOUNT_SID=think_elearn_account_sid_here
TWILIO_AUTH_TOKEN=think_elearn_auth_token_here
TWILIO_PHONE_NUMBER=+12898163749
```

**Where to find these values:**

- **Account SID & Auth Token**: Twilio Console → Dashboard
- **Phone Number**: Your purchased Twilio number (e.g., +12898163749)

### 3. Configure Twilio Phone Number

1. **Voice Configuration**
   - Navigate to Phone Numbers → Manage → Active numbers
   - Click on your phone number
   - In the Voice section:
     - **A call comes in**: Select "TwiML Bin" and choose your created TwiML Bin
   - Save configuration

2. **SMS Configuration**
   - In the Messaging section:
     - **A message comes in**: Webhook
     - **URL**: `https://web-production-17c5.up.railway.app/communications/sms-webhook`
     - **HTTP Method**: POST
   - Save configuration

### 4. Webhook Endpoints

The Django application provides two webhook endpoints:

#### Voicemail Webhook

- **URL**: `/communications/handle-recording`
- **Method**: POST
- **Purpose**: Receives voicemail recording data from Twilio
- **Response**: TwiML thanking caller and hanging up

#### SMS Webhook

- **URL**: `/communications/sms-webhook`
- **Method**: POST
- **Purpose**: Receives SMS message data from Twilio
- **Response**: TwiML auto-reply thanking sender

## Database Models

### VoicemailMessage

Stores voicemail recordings with the following fields:

- `recording_url`: URL to the audio recording
- `recording_sid`: Twilio's unique recording identifier
- `caller_number`: Phone number of the caller
- `duration`: Length of recording in seconds
- `transcription`: Auto-transcription (if enabled in Twilio)
- `created_at`: Timestamp of the call

### SMSMessage

Stores SMS messages with the following fields:

- `message_sid`: Twilio's unique message identifier
- `from_number`: Sender's phone number
- `to_number`: Recipient's phone number (your Twilio number)
- `body`: Message content
- `media_url`: URL to attached media (if any)
- `created_at`: Timestamp of the message

## Admin Interface

Both models are registered with Django admin for easy management:

1. **Access**: Navigate to `/admin/` and log in
2. **View Messages**:
   - Communications → Voicemail messages
   - Communications → SMS messages
3. **Features**:
   - Search by phone number or content
   - Filter by date
   - Read-only access to Twilio IDs and timestamps

## Call Flow

### Incoming Voice Call

1. Call received by Twilio number
2. TwiML Bin executes:
   - Attempts to dial +14169093199 (your actual number) for 20 seconds
   - If no answer, plays greeting messages
   - Records voicemail (max 60 seconds)
   - Posts recording data to `/communications/handle-recording`
3. Django webhook:
   - Saves voicemail to database
   - Returns TwiML response thanking caller
   - Hangs up the call

### Incoming SMS

1. SMS received by Twilio number
2. Twilio posts message data to `/communications/sms-webhook`
3. Django webhook:
   - Saves message to database
   - Returns auto-reply: "Thank you for your message! We'll get back to you soon."

## Security Considerations

1. **Webhook Authentication**: Consider adding Twilio signature validation for production
2. **Environment Variables**: Never commit Twilio credentials to version control
3. **HTTPS**: Always use HTTPS URLs for webhook endpoints
4. **Admin Access**: Restrict Django admin access to authorized users only

## Testing

### Test Voice Calls

1. Call your Twilio number
2. Let it go to voicemail
3. Leave a test message
4. Check Django admin for the recorded message

### Test SMS

1. Send an SMS to your Twilio number
2. Check Django admin for the received message
3. Verify auto-reply was sent

## Troubleshooting

### Common Issues

1. **Webhook not receiving data**
   - Verify URLs are correct and accessible
   - Check Railway deployment is running
   - Ensure HTTPS is used

2. **Environment variables not working**
   - Verify variables are set in Railway dashboard
   - Restart the application after setting variables

3. **Database errors**
   - Ensure migrations are applied: `python manage.py migrate`
   - Check database connectivity

### Debugging

1. **Check Twilio Debugger**
   - Navigate to Monitor → Debugger in Twilio Console
   - Look for webhook request errors

2. **Django Logs**
   - Check Railway logs for Django errors
   - Add logging to webhook views if needed

## Cost Considerations

- **Voice calls**: ~$0.013/minute for incoming calls
- **SMS**: ~$0.0075 per message
- **Phone number**: ~$1.15/month
- **Recordings**: Storage costs apply for longer recordings

## Future Enhancements

1. **Transcription**: Enable Twilio's automatic transcription service
2. **Notifications**: Send email alerts for new voicemails/SMS
3. **Two-way SMS**: Implement replies from Django admin
4. **Call forwarding**: Dynamic forwarding based on business hours
5. **Analytics**: Track call volumes and response times
