# Railway Email Setup - Quick Reference

## Problem

Railway blocks SMTP ports (25, 465, 587) on Free/Hobby/Trial plans, preventing email sending via traditional SMTP.

## Solution

Use Mailtrap API (HTTPS-based) instead of SMTP.

## Setup (5 minutes)

### Step 1: Get Mailtrap API Token

1. Go to [mailtrap.io](https://mailtrap.io/)
2. Login/signup
3. Navigate to **Sending Domains** → **API Tokens**
4. Copy your API token
5. Verify domain: `thinkelearn.com`

### Step 2: Add to Railway

1. Open Railway project dashboard
2. Go to **Variables** tab
3. Add new variable:
   - **Name**: `MAILTRAP_API_TOKEN`
   - **Value**: `<paste-your-token-here>`
4. Save (Railway will auto-redeploy)

### Step 3: Test

```bash
railway shell
python test_email.py
```

Enter a test email address and verify delivery.

## That's It!

No code changes needed. The custom backend handles everything automatically.

## Verification

After deployment, check Railway logs:

```bash
railway logs
```

Look for:
```
Email sent via Mailtrap API: <response>
```

## Troubleshooting

**Email not sending?**

1. Check token is set: `railway variables`
2. Verify domain in Mailtrap dashboard
3. Check logs: `railway logs --follow`

**Still using SMTP?**

The system falls back to SMTP if `MAILTRAP_API_TOKEN` is not set. Make sure the variable is added in Railway dashboard.

## Environment Variables Summary

**Required**:
- `MAILTRAP_API_TOKEN` - Your Mailtrap API token

**Optional** (has defaults):
- `DEFAULT_FROM_EMAIL` - Defaults to `hello@thinkelearn.com`

## Cost

- **Mailtrap Free**: 1,000 emails/month
- **Mailtrap Pro**: Higher limits if needed

## Documentation

For detailed information, see:
- `docs/mailtrap-setup.md` - Complete setup guide
- `MAILTRAP_SETUP_COMPLETE.md` - Implementation summary

---

**Ready to deploy?** Just add `MAILTRAP_API_TOKEN` to Railway and you're done! ✅
