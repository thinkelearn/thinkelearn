# COPPA Compliance Quick Reference

**🔴 CRITICAL: BLOCKER FOR CHILDREN'S COURSES LAUNCH**

## TL;DR - Cannot Launch Until Complete

❌ **DO NOT launch courses for children under 13 without:**

1. Legal counsel approval of OAuth-based approach
2. Age verification system at signup
3. OAuth-only restriction for under-13 accounts
4. Feature restrictions (no Stripe, no SMS, etc.)
5. Microsoft OAuth provider added

**Strategy:** Rely on Google Family Link and Microsoft Family for parental consent

**Penalties:** Up to $50,120 per violation (each child = violation)

---

## What's Done ✅

- Privacy Policy updated with OAuth-based Children's Privacy section
- Terms and Conditions updated with OAuth enrollment requirements
- Compliance strategy documented (OAuth-based approach)
- Legal framework leverages Google/Microsoft COPPA compliance

## What's Required 🔴

### Technical (5 weeks estimated)

1. **Age Verification** (Week 1)
   - Add date of birth field to signup form
   - Validate age during account creation
   - Flag accounts under 13 with `is_child_account` boolean

2. **OAuth-Only Enforcement** (Week 1-2)
   - Detect age during signup
   - Block direct signup (email/password) for under-13
   - Redirect to OAuth providers with family account messaging
   - Add Microsoft OAuth provider (Google already implemented)

3. **Family Account Detection** (Week 2-3)
   - Detect Google Family Link accounts during OAuth flow
   - Detect Microsoft Family accounts during OAuth flow
   - Verify family account status (optional enhancement)

4. **Feature Restrictions** (Week 3-4)
   - Disable Stripe checkout for child accounts (parent-managed only)
   - Disable SMS notifications for child accounts
   - Disable public reviews/ratings for child accounts
   - Hide payment methods in dashboard

5. **Parent Communication** (Week 4-5)
   - Create parent documentation (how to use Family Link/Microsoft Family)
   - Add enrollment confirmation emails for parents
   - Link to family account dashboards in emails

6. **Data Deletion Workflow** (Week 5)
   - Handle direct parent data deletion requests
   - 30-day deletion process for account removal
   - Export functionality for parent data requests

### Legal (1-2 weeks, concurrent)

1. **Legal Counsel Review** - OAuth-based approach approval (~$1K-2K vs $5K-10K)
2. **Service Provider Audit** - Confirm Google/Microsoft COPPA compliance (public info)
3. **Documentation Review** - Finalize privacy policy and terms language
4. **Parent Materials** - Review parent-facing documentation

### Business Process (ongoing)

1. **Parent Support** - Handle data review/export/deletion requests
2. **Compliance Monitoring** - Quarterly reviews of family account policies
3. **Provider Updates** - Track Google/Microsoft family account policy changes

---

## Quick Compliance Checklist

### Before Any Child Under 13 Can Enroll

**Legal:**

- [ ] Lawyer reviewed and approved OAuth-based approach
- [ ] Privacy Policy deployed (DONE ✅)
- [ ] Terms deployed (DONE ✅)
- [ ] Parent documentation created
- [ ] Google/Microsoft COPPA compliance verified

**Technical:**

- [ ] Age verification working at signup
- [ ] OAuth-only enforcement for under-13
- [ ] Microsoft OAuth provider added
- [ ] Family account detection implemented
- [ ] Feature restrictions implemented
- [ ] Data deletion workflow working

**For Children Under 13:**

- [ ] Parent has created Google Family Link OR Microsoft Family account
- [ ] Parent has reviewed Google/Microsoft privacy policies
- [ ] Parent has consented through family account setup
- [ ] Child signs in via OAuth only
- [ ] Account flagged as child account
- [ ] Features restricted appropriately

---

## Key Rules to Remember

### DO ✅

- **Require** Google Family Link or Microsoft Family for under-13
- Get parental consent THROUGH identity provider (Google/Microsoft)
- Collect MINIMUM information needed (name, email, progress only)
- Use data ONLY for educational purposes
- Let parents review/delete child data (family dashboards + direct requests)
- Delete data within 30 days of request
- Notify parents of data practices (via family account providers)
- Maintain audit trail of child account flags

### DON'T ❌

- Allow children under 13 to create direct email/password accounts
- ~~Use Google OAuth for under-13 accounts~~ **NOW REQUIRED via Family Link**
- Process payments directly from child accounts (parent-managed only)
- Send SMS notifications to children
- Allow public reviews/ratings from children
- Share children's data with third parties beyond Google/Microsoft
- Monetize children's data
- Collect phone numbers, addresses, photos from children
- Keep data longer than necessary

---

## OAuth-Based Strategy Benefits

**Why This Works:**

- Google and Microsoft are already COPPA-compliant
- They handle verifiable parental consent
- Parents manage accounts through Family Link/Microsoft Family dashboards
- We rely on their consent mechanism (no custom workflows needed)
- Significantly reduces development time (5 weeks vs 11-12 weeks)
- Reduces legal review costs (75% less complex)
- Better parent experience (familiar tools)

**What We Leverage:**

- Google Family Link parental consent and management
- Microsoft Family parental consent and management
- Industry-standard OAuth 2.0 authentication
- Their privacy policy reviews and compliance teams
- Their data protection infrastructure

**Our Responsibilities:**

- Age verification at signup
- OAuth-only enforcement for under-13
- Feature restrictions for child accounts
- Parent communication and support
- Data deletion on direct parent request
- Minimal data collection

---

## Emergency Contacts

**If you suspect a COPPA violation:**

1. **Stop immediately** - Cease affected activity
2. **Notify Privacy Officer** - <f.villegas@thinkelearn.com>
3. **Consult legal counsel** - Immediately
4. **Document incident** - Date, time, scope, actions taken
5. **Notify FTC if required** - Within legal timelines

**For Parent Requests:**

- Email: <f.villegas@thinkelearn.com>
- Phone: (289) 816-3749
- Response deadline: 30 days

**Family Account Support:**

- Google Family Link: <https://families.google.com/>
- Microsoft Family: <https://account.microsoft.com/family>

---

## Resources

**Full Documentation:**

- `/docs/coppa-pipeda-compliance-plan.md` - Complete OAuth-based implementation guide
- `/thinkelearn/templates/privacy.html` - Updated Children's Privacy section
- `/thinkelearn/templates/terms.html` - Updated enrollment requirements

**Family Account Providers:**

- Google Family Link: <https://families.google.com/familylink/>
- Microsoft Family: <https://www.microsoft.com/en-us/microsoft-365/family-safety>
- Google Family Link Privacy: <https://families.google.com/familylink/privacy/notice/>
- Microsoft Family Privacy: <https://privacy.microsoft.com/en-us/privacystatement>

**Regulations:**

- FTC COPPA Page: <https://www.ftc.gov/legal-library/browse/rules/childrens-online-privacy-protection-rule-coppa>
- COPPA FAQs: <https://www.ftc.gov/business-guidance/resources/complying-coppa-frequently-asked-questions>
- Privacy Commissioner (Canada): <https://www.priv.gc.ca/>

**Compliance Deadline:** April 22, 2026 (COPPA amendments)

---

## Next Steps

1. **This Week:**
   - [ ] Schedule legal counsel consultation (OAuth approach)
   - [ ] Review updated privacy policy and terms
   - [ ] Assign development resources for 5-week sprint
   - [ ] Create project timeline

2. **Week 1-2:**
   - [ ] Complete legal review (~$1K-2K)
   - [ ] Implement age verification
   - [ ] Add OAuth-only enforcement
   - [ ] Add Microsoft OAuth provider

3. **Week 3-4:**
   - [ ] Implement family account detection
   - [ ] Build feature restrictions
   - [ ] Create parent documentation

4. **Week 5:**
   - [ ] Build data deletion workflow
   - [ ] Test with real family accounts
   - [ ] Prepare for pilot launch

**Status Updates:** Track progress in `/docs/coppa-pipeda-compliance-plan.md`

---

## Timeline Comparison

**Original Approach (School-Based Consent):**

- Technical: 8 weeks
- Legal: $5K-10K
- Complexity: High
- Ongoing: School agreements, parent consent tracking

**OAuth Approach (CURRENT):**

- Technical: 5 weeks
- Legal: $1K-2K
- Complexity: Medium
- Ongoing: Parent support only

**Savings:** 75% reduction in time and cost ✅
