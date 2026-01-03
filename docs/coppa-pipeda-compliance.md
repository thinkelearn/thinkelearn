# COPPA & PIPEDA Compliance - OAuth-Only Strategy

**Status:** ✅ Ready for Legal Review
**Cost:** $1.5K-3K total (95% cheaper than alternatives)
**Timeline:** 2 days implementation + legal review
**Last Updated:** January 2, 2026

---

## Strategy: OAuth-Only for Everyone

We don't ask, don't store, and don't need to know users' ages.

- **All users** authenticate via Google or Microsoft OAuth (no email/password accounts)
- **No date of birth collection** - we never receive or store age information
- **No age-based restrictions** - all users treated equally
- **For children under 13**: Parents manage access via Google Family Link or Microsoft Family Safety
- **For adults**: Standard Google/Microsoft accounts work normally

**Why this works:** COPPA requires appropriate handling when we have "actual knowledge" of collecting from children. By not collecting DOB and using OAuth-only, we avoid having actual knowledge while ensuring children can only access through COPPA-compliant parent-managed accounts.

---

## Implementation Checklist

### Technical (2 days)

- [ ] Disable direct email/password signup in templates
- [ ] Add Microsoft OAuth provider to django-allauth
- [ ] Register app in Azure Active Directory
- [ ] Add `MICROSOFT_CLIENT_ID` and `MICROSOFT_CLIENT_SECRET` env vars
- [ ] Test both OAuth flows (Google + Microsoft)
- [ ] Create parent help page explaining family accounts

### Legal (1-2 weeks)

- [ ] Privacy lawyer consultation (~$500-1K)
- [ ] Review OAuth-only approach
- [ ] Privacy Policy updated (explain OAuth-only)
- [ ] Terms updated (explain OAuth-only)
- [ ] Written legal approval

### Business Process

- [ ] Privacy Officer designated: f.villegas@thinkelearn.com
- [ ] Parent data deletion process documented (30-day response)
- [ ] Monitor provider policy changes (quarterly)

---

## Technical Implementation

### 1. Microsoft OAuth Setup

```python
# thinkelearn/settings/base.py

INSTALLED_APPS = [
    # ... existing
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.microsoft',  # Add this
]

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    },
    'microsoft': {
        'SCOPE': ['User.Read'],
    }
}
```

Environment variables:
- `MICROSOFT_CLIENT_ID` - from Azure portal
- `MICROSOFT_CLIENT_SECRET` - from Azure portal

### 2. Update Signup Template

```html
<!-- templates/account/signup.html -->
<div class="bg-cyan-50 border-l-4 border-cyan-500 p-4 mb-6">
    <p><strong>Sign up with your Google or Microsoft account</strong></p>
    <p class="text-sm">OAuth-only for better security and privacy. No passwords!</p>
</div>

<a href="{% provider_login_url 'google' %}" class="btn">Continue with Google</a>
<a href="{% provider_login_url 'microsoft' %}" class="btn">Continue with Microsoft</a>

<p class="text-sm mt-6">
    <strong>For parents of children under 13:</strong><br>
    Use <a href="https://families.google.com/familylink">Google Family Link</a>
    or <a href="https://account.microsoft.com/family">Microsoft Family Safety</a>
</p>
```

### 3. UserAccount Model (example implementation)

**Use this model (or add equivalent fields to your existing user model) to support the required parent data-deletion workflow and any additional profile fields beyond name/email.**

```python
# thinkelearn/models.py

from django.conf import settings
from django.db import models

class UserAccount(models.Model):
    """
    Optional profile extension. Named UserAccount to avoid
    Wagtail's UserProfile conflict.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='account_profile'
    )

    # Optional deletion tracking for parent requests
    pending_deletion = models.BooleanField(default=False)
    deletion_requested_at = models.DateTimeField(null=True, blank=True)

    # Add other fields as needed:
    # preferred_language = models.CharField(max_length=10, default='en')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def mark_for_deletion(self):
        from django.utils import timezone
        self.pending_deletion = True
        self.deletion_requested_at = timezone.now()
        self.save()
```

---

## What We DON'T Need

❌ Custom User model extending AbstractUser
❌ Date of birth field
❌ `is_child_account` boolean flag
❌ Age calculation methods
❌ Signup form age validation
❌ Age-based feature restrictions
❌ OAuth signal handlers for child detection
❌ Birthday transition logic

---

## Legal Compliance Rationale

**COPPA:** Doesn't require knowing ages. Requires appropriate handling when we have "actual knowledge" of collecting from children. By not collecting DOB, we avoid actual knowledge while ensuring children access only through COPPA-compliant family accounts.

**PIPEDA:** Requires consent for data collection. For children: parent consent via Google/Microsoft family account setup. For adults: their own consent via OAuth.

**Key principles:**
- Don't ask for age
- Don't store age
- Don't infer age
- Don't need to know age
- Rely on industry-leading COPPA-compliant providers

---

## Data Collection

**What we collect (same for all users):**
- Name (from OAuth)
- Email (from OAuth)
- Course enrollments
- Learning progress
- SCORM tracking data

**What we DON'T collect:**
- Dates of birth
- Passwords (OAuth-only)
- Phone numbers
- Addresses
- Photos/videos
- Geolocation
- Government IDs

**How we use data:**
- Educational purposes only
- No marketing to anyone
- No third-party sharing (except Google/Microsoft for auth)

---

## Parent Rights

Parents can:
- Manage access via Google Family Link or Microsoft Family Safety dashboards
- Revoke access anytime through provider
- Request data review/export/deletion by contacting f.villegas@thinkelearn.com
- We respond within 30 days

---

## Risk Assessment

**Low Risk:**
- OAuth provider changes policies → Monitor quarterly, legal review if needed
- Users don't have Google/Microsoft → Very rare, accounts extremely common
- Parent data requests exceed capacity → Simple export/deletion via Django admin

**Very Low Risk:**
- Legal interpretation changes → OAuth-only exceeds minimum COPPA requirements
- Provider loses COPPA compliance → Core to their business, highly unlikely

---

## Resources

**Providers:**
- Google Family Link: https://families.google.com/familylink
- Microsoft Family Safety: https://account.microsoft.com/family

**Regulations:**
- COPPA: https://www.ftc.gov/legal-library/browse/rules/childrens-online-privacy-protection-rule-coppa
- PIPEDA: https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/

**Legal Help:**
- Privacy lawyers specializing in EdTech
- Canadian firms with U.S. COPPA experience

---

## Summary

OAuth-only authentication provides the simplest, most defensible approach to COPPA/PIPEDA compliance:

- ✅ 95% reduction in development time (2 days vs 8-12 weeks)
- ✅ 90% reduction in legal costs ($500-1K vs $5K-10K)
- ✅ Better privacy (minimal PII collection)
- ✅ Better security (no passwords, OAuth 2FA)
- ✅ Simpler architecture (no age tracking)
- ✅ Lower legal risk (avoid being age verification system)

**Next steps:**
1. Implement OAuth-only (2 days)
2. Legal review ($500-1K)
3. Launch!

**Contact:** f.villegas@thinkelearn.com
