# Mailtrap API Setup Guide

This guide explains how to set up Mailtrap API for email sending on Railway.

## Why Mailtrap API Instead of SMTP?

Railway restricts outbound SMTP access on Free/Hobby/Trial plans to prevent spam. SMTP ports (25, 465, 587) are blocked by default. The solution is to use HTTPS API-based email services like Mailtrap.

## Setup Steps

### 1. Get Your Mailtrap API Token

1. Log in to [Mailtrap](https://mailtrap.io/)
2. Navigate to **Sending Domains** or **API Tokens**
3. Create or copy your API token
4. Verify your sending domain (hello@thinkelearn.com)

### 2. Configure Railway Environment Variables

Add the following environment variable in your Railway project:

```bash
MAILTRAP_API_TOKEN=<your-api-token-here>
```

**Optional environment variables:**

```bash
DEFAULT_FROM_EMAIL=hello@thinkelearn.com
```

### 3. Deploy to Railway

Once you've added the environment variable:

1. Railway will automatically redeploy
2. The new Mailtrap API backend will be used
3. Emails will be sent via HTTPS API instead of SMTP

### 4. Test Email Sending

After deployment, test the email functionality:

```bash
# SSH into Railway container
railway run python test_email.py

# Or use Railway shell
railway shell
python test_email.py
```

## How It Works

### Custom Email Backend

The project includes a custom Django email backend at `thinkelearn/backends/mailtrap.py` that:

1. Converts Django `EmailMessage` objects to Mailtrap `Mail` objects
2. Sends emails via Mailtrap's HTTPS API
3. Supports HTML emails (EmailMultiAlternatives)
4. Handles CC, BCC, and multiple recipients
5. Includes error handling and logging

### Configuration

In `thinkelearn/settings/production.py`:

```python
# Use Mailtrap API backend instead of SMTP
EMAIL_BACKEND = "thinkelearn.backends.mailtrap.MailtrapAPIBackend"
MAILTRAP_API_TOKEN = os.environ.get("MAILTRAP_API_TOKEN")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "hello@thinkelearn.com")

# Fallback to SMTP if MAILTRAP_API_TOKEN not set (backward compatibility)
if not MAILTRAP_API_TOKEN:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    # ... SMTP settings ...
```

### Backward Compatibility

If `MAILTRAP_API_TOKEN` is not set, the system automatically falls back to SMTP configuration. This ensures:

- Development environments continue to work
- Easy rollback if needed
- Gradual migration path

## Usage Examples

### Simple Email

```python
from django.core.mail import send_mail

send_mail(
    subject="Test Email",
    message="This is a test email.",
    from_email="hello@thinkelearn.com",
    recipient_list=["user@example.com"],
)
```

### HTML Email

```python
from django.core.mail import EmailMultiAlternatives

email = EmailMultiAlternatives(
    subject="Test Email",
    body="Plain text version",
    from_email="hello@thinkelearn.com",
    to=["user@example.com"],
)
email.attach_alternative("<h1>HTML version</h1>", "text/html")
email.send()
```

### Contact Form (Existing Code)

The existing contact form in `home/models.py` will automatically use the Mailtrap API backend with no code changes required.

## Troubleshooting

### Email Not Sending

1. **Verify API token is set**: Check Railway environment variables
2. **Check sender domain**: Ensure `hello@thinkelearn.com` is verified in Mailtrap
3. **View logs**: Check Railway logs for detailed error messages
4. **Test locally**: Use `python test_email.py` to test configuration

### Common Errors

**"MAILTRAP_API_TOKEN setting is required"**
- The API token is not set in Railway environment variables
- Add the token and redeploy

**"Authentication failed"**
- The API token is invalid or expired
- Get a new token from Mailtrap dashboard

**"Sender domain not verified"**
- The sender email domain is not verified in Mailtrap
- Verify `thinkelearn.com` domain in Mailtrap

## Benefits of Mailtrap API

1. **Works on Railway Free/Hobby plans**: No SMTP port restrictions
2. **Better deliverability**: HTTPS API is more reliable than SMTP
3. **Advanced features**: Email analytics, testing, and monitoring
4. **No timeout issues**: No connection timeout problems like SMTP
5. **Easy debugging**: Clear API responses and error messages

## Cost Considerations

- **Mailtrap Free Tier**: 1,000 emails/month (sufficient for most small projects)
- **Mailtrap Pro**: Higher limits for growing projects
- **Railway**: Works on all Railway plans (Free/Hobby/Trial/Pro)

## Migration Path

If you need to switch email providers in the future:

1. Create a new email backend in `thinkelearn/backends/`
2. Update `EMAIL_BACKEND` in production settings
3. Add required environment variables
4. Deploy and test

The existing email sending code throughout the project will continue to work without changes.
