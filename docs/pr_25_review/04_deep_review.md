# PR #25 Deep Review

## home/tests/test_navigation_integration.py

### High-level review

- These are good, focused accessibility/integration checks. However, the tests currently
  depend on a manually running server, hard-coded credentials, and a brittle login flow.
  That will be flaky in CI and leaks secrets.
- Use Django's live_server and pytest-django to run against the test database, create a
  user fixture, and authenticate either via Django's TestClient and session cookie
  injection or by UI with generated creds. Avoid hard-coded emails/passwords.
- Remove broad networkidle waits; rely on expect() to wait for visible/hidden states.
- The chevron "rotate(180deg)" assertion is brittle (inline style). Prefer testing for a
  deterministic class toggle or computed state tied to aria-expanded.
- Mark DB usage and ensure transactional isolation.

### Inline comments and fixes

#### authenticated_page fixture

- Issue: Hard-coded hostname and credentials cause flakiness and secret leakage; depends
  on an external server.
- Fix: Use live_server from pytest-django and generate a test user. Prefer authenticating
  by injecting the Django session cookie into the Playwright context to skip the login UI.
  Also mark DB usage at module level.

Suggested replacement:

```python
from urllib.parse import urlparse

import pytest
from django.contrib.auth import get_user_model

pytestmark = [pytest.mark.django_db(transaction=True)]

@pytest.fixture
def user(django_user_model):
    # Create a user with deterministic credentials for UI tests
    return django_user_model.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="test-pass-123",
    )

@pytest.fixture
def authenticated_page(page, context, live_server, client, user):
    # Log in via Django test client to avoid flaky UI login and speed up tests
    assert client.login(username=user.username, password="test-pass-123")
    # Extract sessionid from the test client and apply it to Playwright
    session_cookie = client.cookies["sessionid"].value
    parsed = urlparse(live_server.url)
    context.add_cookies(
        [
            {
                "name": "sessionid",
                "value": session_cookie,
                "domain": parsed.hostname,
                "path": "/",
                "httpOnly": True,
                "sameSite": "Lax",
            }
        ]
    )
    # Navigate somewhere that renders the user menu
    page.goto(f"{live_server.url}/")
    # Ensure the button is present before returning
    expect(page.locator("#user-menu-button")).to_be_visible()
    return page
```

Notes:

- If your auth uses email as the login field (e.g., allauth), set
  client.login(email=..., password=...) or client.post to the login endpoint accordingly.
- If your login requires CSRF for POST, the client.login helper avoids UI needs.

#### page.goto(...), page.wait_for_url(..., wait_until="networkidle")

- Issue: Ties to localhost, and networkidle is a broad, brittle wait that can
  intermittently hang.
- Fix: Use live_server.url, and use expect on specific elements (e.g., the menu button)
  or expect(page).to_have_url(re.compile(...)) with a known path.

Example:

```python
page.goto(f"{live_server.url}/")
expect(page.locator("#user-menu-button")).to_be_visible()
```

#### test_chevron_rotates_when_dropdown_opens

- Issue: icon.evaluate("el => el.style.transform") will often be empty if rotation is
  applied via CSS classes or computed style, causing false negatives. Also, immediate
  reads can race with CSS transitions.
- Fix: Assert on a stable class toggle bound to state, or computed class derived from
  aria-expanded. If you use Tailwind or your own class toggling, assert via to_have_class
  with regex. As a fallback, assert aria-expanded only and remove the brittle transform
  check.

Option A (class-based, recommended if applicable):

```python
def test_chevron_rotates_when_dropdown_opens(self, authenticated_page: Page):
    button = authenticated_page.locator("#user-menu-button")
    icon = authenticated_page.locator("#user-menu-icon")

    # Open dropdown
    button.click()
    # Wait for state to apply
    expect(button).to_have_attribute("aria-expanded", "true")
    # Expect rotation class present (adjust class name to your implementation)
    expect(icon).to_have_class(re.compile(r"\brotate-180\b"))

    # Close dropdown
    button.click()
    expect(button).to_have_attribute("aria-expanded", "false")
    # Rotation class removed or replaced with base state
    expect(icon).not_to_have_class(re.compile(r"\brotate-180\b"))
```

Option B: Remove brittle test and rely on aria-expanded which you already assert
elsewhere.

#### test_dropdown_closes_on_outside_click

- Issue: Clicking body at x=10,y=10 may hit an element or be consumed by layout; this
  can be flaky.
- Fix: Prefer clicking on a container you control (e.g., main) or use page.mouse.click
  at coordinates known to be outside the menu. Alternatively, press Escape which is a
  more deterministic close, but that duplicates Escape test.

Example:

```python
authenticated_page.locator("main").click()  # or header/footer wrapper
# or
authenticated_page.mouse.click(1, 1)
```

#### test_dropdown_works_on_mobile_viewport

- Issue: Changing viewport mid-test can be okay, but it is more stable to create a
  dedicated mobile context and page for this test so layout is correct from the start.
- Fix: Add a mobile_page fixture that uses browser.new_context(viewport=...), then close
  it after. Keeps isolation and mirrors actual device behavior.

Example fixture:

```python
@pytest.fixture
def mobile_page(browser, live_server, context, client, user):
    # log in via client and set cookie as shown earlier
    new_context = browser.new_context(viewport={"width": 375, "height": 667})
    # Add session cookie to new context
    from urllib.parse import urlparse
    client.login(username=user.username, password="test-pass-123")
    session_cookie = client.cookies["sessionid"].value
    parsed = urlparse(live_server.url)
    new_context.add_cookies(
        [
            {
                "name": "sessionid",
                "value": session_cookie,
                "domain": parsed.hostname,
                "path": "/",
                "httpOnly": True,
                "sameSite": "Lax",
            }
        ]
    )
    p = new_context.new_page()
    p.goto(f"{live_server.url}/")
    yield p
    new_context.close()
```

And update the test:

```python
def test_dropdown_works_on_mobile_viewport(self, mobile_page: Page):
    button = mobile_page.locator("#user-menu-button")
    dropdown = mobile_page.locator("#user-menu-dropdown")
    button.click()
    expect(dropdown).not_to_have_class(re.compile(r"\bhidden\b"))
    button.click()
    expect(dropdown).to_have_class(re.compile(r"\bhidden\b"))
```

#### General: waiting and selectors

- Prefer role-based selectors for accessibility and resilience where practical:
  - button = page.get_by_role("button", name=re.compile("user menu", re.I)) if you have
    an accessible name.
  - menu = page.get_by_role("menu")
  - items = page.get_by_role("menuitem")
- You can still keep ID-based selectors if these are stable across the app; role-based
  selectors help ensure you're testing the accessible contract.

#### test_menu_items_have_role_menuitem

- Note: Asserting exactly 3 may become brittle as the product grows or varies by
  permissions. If that is by design, keep it; otherwise assert a minimum expected set
  or assert specific items by name.

#### Focus management tests

- Good coverage. To reduce flakes, ensure the dropdown is open and items are visible
  before focusing or pressing arrow keys:
  - expect(dropdown).to_be_visible() before focusing items.

#### Transactions and isolation

- Add pytestmark = [pytest.mark.django_db(transaction=True)] at module level to ensure
  session creation via client and live_server operate on the same DB and are properly
  isolated between tests.

#### Security/authz

- Avoid hard-coded real credentials. Use generated test users in DB.
- If the dropdown content depends on permissions, consider adding a parametric test with
  a user lacking permissions to verify items are hidden.

### Proposed revised file (abridged to show key changes)

```python
"""
Integration tests for navigation dropdown accessibility.
"""

import re
from urllib.parse import urlparse

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.django_db(transaction=True)]

@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="test-pass-123",
    )

@pytest.fixture
def authenticated_page(page: Page, context, live_server, client, user):
    assert client.login(username=user.username, password="test-pass-123")
    session_cookie = client.cookies["sessionid"].value
    parsed = urlparse(live_server.url)
    context.add_cookies(
        [
            {
                "name": "sessionid",
                "value": session_cookie,
                "domain": parsed.hostname,
                "path": "/",
                "httpOnly": True,
                "sameSite": "Lax",
            }
        ]
    )
    page.goto(f"{live_server.url}/")
    expect(page.locator("#user-menu-button")).to_be_visible()
    return page

class TestNavigationDropdown:
    def test_dropdown_button_has_aria_attributes(self, authenticated_page: Page):
        button = authenticated_page.locator("#user-menu-button")
        expect(button).to_have_attribute("aria-expanded", "false")
        expect(button).to_have_attribute("aria-haspopup", "true")
        expect(button).to_have_attribute("aria-controls", "user-menu-dropdown")

    def test_dropdown_menu_has_role_attribute(self, authenticated_page: Page):
        dropdown = authenticated_page.locator("#user-menu-dropdown")
        expect(dropdown).to_have_attribute("role", "menu")
        expect(dropdown).to_have_attribute("aria-orientation", "vertical")
        expect(dropdown).to_have_attribute("aria-labelledby", "user-menu-button")

    def test_menu_items_have_role_menuitem(self, authenticated_page: Page):
        menu_items = authenticated_page.locator('#user-menu-dropdown a[role="menuitem"]')
        expect(menu_items).to_have_count(3)

    def test_dropdown_opens_on_click(self, authenticated_page: Page):
        button = authenticated_page.locator("#user-menu-button")
        dropdown = authenticated_page.locator("#user-menu-dropdown")
        expect(dropdown).to_have_class(re.compile(r"\bhidden\b"))
        button.click()
        expect(dropdown).not_to_have_class(re.compile(r"\bhidden\b"))
        expect(button).to_have_attribute("aria-expanded", "true")

    def test_dropdown_closes_on_second_click(self, authenticated_page: Page):
        button = authenticated_page.locator("#user-menu-button")
        dropdown = authenticated_page.locator("#user-menu-dropdown")
        button.click()
        expect(dropdown).not_to_have_class(re.compile(r"\bhidden\b"))
        button.click()
        expect(dropdown).to_have_class(re.compile(r"\bhidden\b"))
        expect(button).to_have_attribute("aria-expanded", "false")

    def test_dropdown_closes_on_outside_click(self, authenticated_page: Page):
        button = authenticated_page.locator("#user-menu-button")
        dropdown = authenticated_page.locator("#user-menu-dropdown")
        button.click()
        expect(dropdown).not_to_have_class(re.compile(r"\bhidden\b"))
        authenticated_page.mouse.click(1, 1)  # reliably outside
        expect(dropdown).to_have_class(re.compile(r"\bhidden\b"))
        expect(button).to_have_attribute("aria-expanded", "false")

    def test_chevron_rotates_when_dropdown_opens(self, authenticated_page: Page):
        button = authenticated_page.locator("#user-menu-button")
        icon = authenticated_page.locator("#user-menu-icon")
        button.click()
        expect(button).to_have_attribute("aria-expanded", "true")
        expect(icon).to_have_class(re.compile(r"\brotate-180\b"))  # adjust per implementation
        button.click()
        expect(button).to_have_attribute("aria-expanded", "false")
        expect(icon).not_to_have_class(re.compile(r"\brotate-180\b"))

    # ... remaining tests unchanged, but ensure dropdown is visible before focusing items:
    # expect(dropdown).not_to_have_class(re.compile(r"\bhidden\b")) before focus/arrow keys
```

Payments/webhooks/accounting:

- Not applicable in this file.

### Summary of must-fix

- Remove hard-coded credentials and localhost dependency. Use live_server and generated
  test users.
- Authenticate via Django TestClient and inject session cookie to Playwright context for
  speed and stability.
- Add pytestmark = django_db(transaction=True).
- Replace networkidle wait with expect on elements/attributes.
- Make the chevron rotation assertion robust (class-based) or remove if purely cosmetic.

---

## lms/admin.py

### High-level

- Admin actions here can mutate financial state (refunds/cancellations). We need stronger
  safeguards: permission gating, atomicity, row locking, and preventing manual edits/
  deletions that break accounting invariants. Also fix message levels and avoid N+1s in
  changelist.

### Inline review comments

1) Imports

- Blocker: message_user(level="warning") passes a string. Django expects a messages level
  int. Import django.contrib.messages and use messages.WARNING (et al).
- Suggestion: import transaction and use transaction.atomic for each transition to ensure
  all-or-nothing per record.
- Suggestion: don't import ValidationError inside methods; import once at top for clarity
  and testability.

1) CourseProductAdmin

- Suggestion: add list_select_related = ("course",) to avoid N+1 on list_display rendering.
- Suggestion: add ordering = ("-updated_at",) and search by course slug if you have it.
- Suggestion: consider autocomplete_fields = ("course",) to avoid large dropdowns.

1) EnrollmentRecordAdmin: query efficiency

- Suggestion: add list_select_related = ("user", "product", "product__course") to reduce
  N+1s on changelist.
- Suggestion: add date_hierarchy = "created_at" and ordering = ("-created_at",) to make
  browsing scalable.

1) EnrollmentRecordAdmin: side effects, atomicity, and concurrency

- Blocker: Each transition might update multiple rows and/or talk to Stripe/ledger. Wrap
  each transition in transaction.atomic(savepoint=True) so partial work does not persist
  if something fails midway.
- Suggestion: Use queryset.select_for_update(of=("self",)) inside an atomic block to
  prevent race conditions when two admins act on the same records. Use per-object atomic
  to allow partial success across the selection without rolling back all.
- Suggestion: Filter the queryset by allowed source statuses before looping. This reduces
  needless exceptions and makes the count messaging accurate and efficient.
- Suggestion: If transition_to triggers refunds with external providers (Stripe), confirm
  it is idempotent and that ledger/totals updates happen atomically within that method.
  If not, the admin action should coordinate idempotency keys and make sure failures
  bubble up.

1) EnrollmentRecordAdmin: permissions and invariants

- Blocker: Users with change permission could refund/cancel. Introduce explicit permission
  gating for these actions (e.g., a custom permission lms.can_manage_enrollments or
  restrict to superusers). Hide actions for users lacking permission via get_actions.
- Blocker: Deleting EnrollmentRecord from admin can corrupt accounting. Disable delete
  and remove the bulk delete action.
- Suggestion: Make fields like amount_paid and status readonly to prevent bypassing
  transition logic via manual edits in the change form. Prefer transitions only.

1) EnrollmentRecordAdmin: UX correctness

- Nit: Update success/error messages to reflect filtered counts (updated vs skipped) and
  use proper message levels.
- Suggestion: autocomplete_fields = ("user", "product") to avoid heavy FKs in admin forms.

### Proposed patch

```diff
diff --git a/lms/admin.py b/lms/admin.py
index e279df4..9bf2c3a 100644
--- a/lms/admin.py
+++ b/lms/admin.py
@@ -1,10 +1,14 @@
 """Admin interface for LMS models"""

 from django.contrib import admin
+from django.contrib import messages
+from django.db import transaction
+from django.core.exceptions import ValidationError

-from .models import CourseProduct, CourseReview, EnrollmentRecord
+from .models import CourseProduct, CourseReview, EnrollmentRecord


 @admin.register(CourseReview)
 class CourseReviewAdmin(admin.ModelAdmin):
@@ -36,6 +40,10 @@ class CourseReviewAdmin(admin.ModelAdmin):
             },
         ),
     )


 @admin.register(CourseProduct)
 class CourseProductAdmin(admin.ModelAdmin):
     """Admin interface for course products"""

     list_display = ("course", "pricing_type", "fixed_price", "is_active", "updated_at")
     list_filter = ("pricing_type", "is_active", "currency")
-    search_fields = ("course__title",)
+    search_fields = ("course__title", "course__slug")
     readonly_fields = ("created_at", "updated_at")
+    list_select_related = ("course",)
+    ordering = ("-updated_at",)
+    autocomplete_fields = ("course",)


 @admin.register(EnrollmentRecord)
 class EnrollmentRecordAdmin(admin.ModelAdmin):
     """Admin interface for enrollment records"""

     list_display = (
         "user",
         "product",
         "status",
         "amount_paid",
         "created_at",
     )
-    list_filter = ("status", "created_at")
+    list_filter = ("status", "created_at")
     search_fields = ("user__username", "product__course__title")
-    readonly_fields = ("created_at", "updated_at")
+    readonly_fields = ("created_at", "updated_at", "status", "amount_paid")
     actions = ["mark_as_cancelled", "mark_as_refunded", "mark_as_payment_failed"]
+    list_select_related = ("user", "product", "product__course")
+    date_hierarchy = "created_at"
+    ordering = ("-created_at",)
+    autocomplete_fields = ("user", "product")

+    def has_delete_permission(self, request, obj=None):
+        # Prevent deletion from admin to protect accounting/ledger invariants.
+        return False
+
+    def get_actions(self, request):
+        actions = super().get_actions(request)
+        # Remove bulk delete
+        actions.pop("delete_selected", None)
+        # Only allow sensitive actions for superusers or users with explicit permission.
+        if not (request.user.is_superuser or request.user.has_perm("lms.can_manage_enrollments")):
+            actions.pop("mark_as_cancelled", None)
+            actions.pop("mark_as_refunded", None)
+            actions.pop("mark_as_payment_failed", None)
+        return actions
+
     @admin.action(description="Mark selected enrollments as cancelled")
     def mark_as_cancelled(self, request, queryset):
         """Bulk action to cancel enrollments"""
-        from django.core.exceptions import ValidationError
-
-        updated = 0
-        errors = 0
-
-        for enrollment in queryset:
-            try:
-                enrollment.transition_to(EnrollmentRecord.Status.CANCELLED)
-                updated += 1
-            except ValidationError:
-                errors += 1
-
-        if updated:
-            self.message_user(
-                request, f"Successfully cancelled {updated} enrollment(s)."
-            )
-        if errors:
-            self.message_user(
-                request,
-                f"Failed to cancel {errors} enrollment(s) due to invalid state transitions.",
-                level="warning",
-            )
+        # Only cancel those that are in a cancellable state to reduce exceptions.
+        qs = queryset.filter(
+            status__in=[
+                EnrollmentRecord.Status.PENDING,
+                EnrollmentRecord.Status.ACTIVE,
+            ]
+        ).select_for_update()
+
+        updated = 0
+        skipped = queryset.count() - qs.count()
+        # Per-object atomic so one failure doesn't roll back others.
+        for enrollment in qs:
+            try:
+                with transaction.atomic():
+                    enrollment.transition_to(EnrollmentRecord.Status.CANCELLED)
+                updated += 1
+            except ValidationError:
+                skipped += 1
+
+        if updated:
+            self.message_user(request, f"Cancelled {updated} enrollment(s).", level=messages.SUCCESS)
+        if skipped:
+            self.message_user(
+                request,
+                f"Skipped {skipped} enrollment(s) due to invalid state or errors.",
+                level=messages.WARNING,
+            )

     @admin.action(description="Mark selected active enrollments as refunded")
     def mark_as_refunded(self, request, queryset):
         """Bulk action to refund active enrollments"""
-        from django.core.exceptions import ValidationError
-
-        updated = 0
-        errors = 0
-
-        for enrollment in queryset:
-            try:
-                enrollment.transition_to(EnrollmentRecord.Status.REFUNDED)
-                updated += 1
-            except ValidationError:
-                errors += 1
-
-        if updated:
-            self.message_user(
-                request, f"Successfully marked {updated} enrollment(s) as refunded."
-            )
-        if errors:
-            self.message_user(
-                request,
-                f"Failed to refund {errors} enrollment(s) - only active enrollments can be refunded.",
-                level="warning",
-            )
+        # Important: transition_to(REFUNDED) must handle provider refunds atomically and idempotently.
+        qs = queryset.filter(status=EnrollmentRecord.Status.ACTIVE).select_for_update()
+        updated = 0
+        skipped = queryset.count() - qs.count()
+        for enrollment in qs:
+            try:
+                with transaction.atomic():
+                    # Consider passing an actor for audit trail if transition_to supports it.
+                    enrollment.transition_to(EnrollmentRecord.Status.REFUNDED)
+                updated += 1
+            except ValidationError:
+                skipped += 1
+
+        if updated:
+            self.message_user(request, f"Marked {updated} enrollment(s) as refunded.", level=messages.SUCCESS)
+        if skipped:
+            self.message_user(
+                request,
+                "Some enrollments were skipped (only ACTIVE enrollments can be refunded or an error occurred).",
+                level=messages.WARNING,
+            )

     @admin.action(description="Mark selected pending enrollments as payment failed")
     def mark_as_payment_failed(self, request, queryset):
         """Bulk action to mark enrollments as payment failed"""
-        from django.core.exceptions import ValidationError
-
-        updated = 0
-        errors = 0
-
-        for enrollment in queryset:
-            try:
-                enrollment.transition_to(EnrollmentRecord.Status.PAYMENT_FAILED)
-                updated += 1
-            except ValidationError:
-                errors += 1
-
-        if updated:
-            self.message_user(
-                request,
-                f"Successfully marked {updated} enrollment(s) as payment failed.",
-            )
-        if errors:
-            self.message_user(
-                request,
-                f"Failed to mark {errors} enrollment(s) - only pending enrollments can be marked as failed.",
-                level="warning",
-            )
+        qs = queryset.filter(status=EnrollmentRecord.Status.PENDING).select_for_update()
+        updated = 0
+        skipped = queryset.count() - qs.count()
+        for enrollment in qs:
+            try:
+                with transaction.atomic():
+                    enrollment.transition_to(EnrollmentRecord.Status.PAYMENT_FAILED)
+                updated += 1
+            except ValidationError:
+                skipped += 1
+
+        if updated:
+            self.message_user(request, f"Marked {updated} enrollment(s) as payment failed.", level=messages.SUCCESS)
+        if skipped:
+            self.message_user(
+                request,
+                "Some enrollments were skipped (only PENDING enrollments can be marked failed or an error occurred).",
+                level=messages.WARNING,
+            )
```

### Notes on Stripe/webhooks/accounting

- Ensure EnrollmentRecord.transition_to handles:
  - For refunds: Stripe refund creation with idempotency key (e.g., using
    enrollment.payment_intent_id or charge id) and deduping on retries.
  - Ledger invariants: amounts should net to zero across payment and refund entries;
    totals on related aggregates updated within the same transaction.atomic.
  - Idempotency across transitions: calling REFUNDED twice should be a no-op and not
    issue a second refund.
- Consider logging the admin actor (request.user) in transition audit trail for
  compliance.

### Optional follow-ups

- Add a custom ModelAdmin form to hide fields that should never be edited and display
  computed fields.
- Add a custom permission to EnrollmentRecord Meta:
  permissions = [("can_manage_enrollments", "Can perform enrollment state transitions")]
  and migrate, then rely on it in get_actions.

---

## lms/migrations/0003_courseproduct_enrollmentrecord_and_more.py

### PR review comments (inline)

- migrations.CreateModel(name="CourseProduct"):
  - Blocking: For financial data integrity, consider CheckConstraints to enforce pricing
    invariants at the DB level:
    - pricing_type="fixed" implies fixed_price > 0.
    - pricing_type="free" implies fixed_price=0 and min_price=0 and suggested_price=0.
    - pricing_type="pwyc" implies 0 <= min_price <= max_price and min_price <=
      suggested_price <= max_price.
  - Concrete fix (add after the model creation):
    - migrations.AddConstraint(model_name="courseproduct",
      constraint=models.CheckConstraint(check=models.Q(pricing_type="fixed",
      fixed_price__gt=0) | ~models.Q(pricing_type="fixed"),
      name="cp_fixed_price_positive_when_fixed"))
    - migrations.AddConstraint(model_name="courseproduct",
      constraint=models.CheckConstraint(check=models.Q(min_price__gte=0,
      max_price__gte=models.F("min_price")), name="cp_min_le_max"))
    - migrations.AddConstraint(model_name="courseproduct",
      constraint=models.CheckConstraint(check=models.Q(pricing_type="pwyc",
      suggested_price__gte=models.F("min_price"),
      suggested_price__lte=models.F("max_price")) | ~models.Q(pricing_type="pwyc"),
      name="cp_suggested_within_range"))
    - migrations.AddConstraint(model_name="courseproduct",
      constraint=models.CheckConstraint(check=models.Q(pricing_type="free",
      fixed_price=0, min_price=0, suggested_price=0) | ~models.Q(pricing_type="free"),
      name="cp_free_prices_zero"))

- CourseProduct.course = OneToOneField(..., on_delete=CASCADE):
  - Suggestion: CASCADE is fine for the product itself, but see EnrollmentRecord.product
    below. Ensure enrollment records are not deleted if course/product is removed.

- migrations.CreateModel(name="EnrollmentRecord"):
  - Blocking: EnrollmentRecord.product and EnrollmentRecord.user use on_delete=CASCADE.
    For payments/accounting history, we should not delete enrollment/payment records
    when a product or user is deleted. Use PROTECT to preserve ledger/audit trail.
  - Concrete fix:
    - product = models.ForeignKey(..., on_delete=django.db.models.deletion.PROTECT,
      related_name="enrollments", to="lms.courseproduct")
    - user = models.ForeignKey(..., on_delete=django.db.models.deletion.PROTECT,
      to=settings.AUTH_USER_MODEL)

- EnrollmentRecord.stripe_checkout_session_id and stripe_payment_intent_id:
  - Blocking: These are declared blank=True but not null=True; this will store empty
    strings, wasting index space and complicating uniqueness. Also, for Stripe
    idempotency you typically need uniqueness guarantees on payment_intent and often
    checkout_session to avoid double-processing.
  - Concrete fix:
    - Make them nullable: models.CharField(null=True, blank=True, max_length=255,
      db_index=True)
    - Add partial unique constraints (PostgreSQL) to enforce uniqueness when present:
      - migrations.AddConstraint(model_name="enrollmentrecord",
        constraint=models.UniqueConstraint(fields=("stripe_payment_intent_id",),
        condition=models.Q(stripe_payment_intent_id__isnull=False),
        name="uniq_enrollment_pi"))
      - migrations.AddConstraint(model_name="enrollmentrecord",
        constraint=models.UniqueConstraint(fields=("stripe_checkout_session_id",),
        condition=models.Q(stripe_checkout_session_id__isnull=False),
        name="uniq_enrollment_cs"))
    - Optionally replace the generic db_index with partial indexes to reduce bloat:
      - migrations.AddIndex(model_name="enrollmentrecord",
        index=models.Index(fields=["stripe_payment_intent_id"], name="enr_pi_idx",
        condition=models.Q(stripe_payment_intent_id__isnull=False)))
      - migrations.AddIndex(model_name="enrollmentrecord",
        index=models.Index(fields=["stripe_checkout_session_id"], name="enr_cs_idx",
        condition=models.Q(stripe_checkout_session_id__isnull=False)))

- EnrollmentRecord.idempotency_key = CharField(unique=True, default=uuid.uuid4):
  - Suggestion: Prefer UUIDField for type-safety and to avoid implicit coercion.
  - Concrete fix:
    - idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True,
      editable=False)

- EnrollmentRecord UniqueConstraint(fields=("user", "product"),
  name="unique_user_product_enrolment"):
  - Blocking: This blocks re-enrollment after a refund/cancel, which is often desirable
    to allow. Use a conditional unique constraint to exclude terminal statuses
    (e.g., cancelled, refunded).
  - Concrete fix:
    - Remove the existing unique constraint and replace with:
      migrations.AddConstraint(
        model_name="enrollmentrecord",
        constraint=models.UniqueConstraint(
          fields=("user", "product"),
          condition=models.Q(~models.Q(status__in=["cancelled", "refunded"])),
          name="uniq_user_product_active_enrollment",
        ),
      )
  - Nit: spelling in the existing name ("enrolment") is inconsistent with model naming;
    if you keep a similar constraint, rename to ..._enrollment.

- EnrollmentRecord.course_enrollment = OneToOneField(..., on_delete=SET_NULL):
  - Suggestion: OneToOne is good for preventing multiple enrollment records from
    pointing to the same CourseEnrollment. Consider a CheckConstraint to reduce data
    inconsistencies, if your DB supports it via triggers or if CourseEnrollment includes
    user/product/course: ensure the linked course_enrollment.user == EnrollmentRecord.user
    and matches the product's course. This can't be enforced easily at the DB level
    with a plain check; document and enforce in application code.

- EnrollmentRecord.amount_paid:
  - Suggestion: Store currency for each EnrollmentRecord to ensure historical
    consistency if CourseProduct currency changes in the future. Even if you only
    support CAD now, adding a currency CharField (default="CAD", choices like
    CourseProduct.currency) prevents ambiguity in ledgers.
  - Concrete fix:
    - currency = models.CharField(max_length=3, choices=[("CAD", "Canadian Dollar")],
      default="CAD")

- Indexes on EnrollmentRecord:
  - Suggestion: The FK to user already has an index. The composite index (user, status)
    is fine. Consider also indexing (product, status) if you frequently query enrollments
    by product and status.
  - Concrete fix:
    - migrations.AddIndex(model_name="enrollmentrecord",
      index=models.Index(fields=["product", "status"],
      name="enr_product_status_idx"))

- Payment and ledger invariants:
  - Suggestion: If you intend to compute revenue/ledger totals from EnrollmentRecord,
    ensure EnrollmentRecord is immutable for amount_paid after becoming active/refunded.
    At minimum, add updated_at, which you have. Consider adding a boolean is_locked or
    using a status transition audit table in future. Not a migration change now, but
    flagging for design.

- CourseProduct.currency choices limited to CAD:
  - Suggestion: Fine for launch; consider referencing a shared currency choices constant
    to avoid divergence with EnrollmentRecord if you add it there.

- Migrations atomicity:
  - OK: No data migrations; schema-only migration will run atomically by default on
    PostgreSQL.

- CourseProduct fixed_price/min_price/suggested_price defaults:
  - Suggestion: For fixed pricing, defaulting fixed_price to 0 can cause accidental
    zero-price products if validations are not enforced at the DB level. The
    CheckConstraints above mitigate this.

- Delete cascades and historical data:
  - Blocking: With current CASCADE on EnrollmentRecord.product and EnrollmentRecord.user,
    deleting a course or user will delete enrollment/payment history, which is a problem
    for accounting and audit. As noted above, switch these to PROTECT. Likewise, consider
    PROTECT on CourseProduct.course to prevent deleting a course with financial data
    attached; alternatively, keep CASCADE on CourseProduct.course but ensure
    EnrollmentRecord.product is PROTECT so enrollments cannot be deleted.

### Concrete patch (summary of key changes)

- Change on_delete for EnrollmentRecord.product and EnrollmentRecord.user to PROTECT.
- Make stripe_* fields nullable and add partial unique constraints and partial indexes.
- Change idempotency_key to UUIDField.
- Replace unique_user_product_enrolment with conditional unique constraint excluding
  cancelled/refunded.
- Add pricing CheckConstraints for CourseProduct.
- Optionally add currency field to EnrollmentRecord.
- Optionally add product+status index.

### Example migration snippets (adapt into this migration before merge; requires

from django.db.models import Q, F)

- Import additions:
  - from django.db.models import Q, F

- EnrollmentRecord field changes:
  - stripe_checkout_session_id = models.CharField(max_length=255, null=True, blank=True)
  - stripe_payment_intent_id = models.CharField(max_length=255, null=True, blank=True)
  - idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
  - product = models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
    related_name="enrollments", to="lms.courseproduct")
  - user = models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
    to=settings.AUTH_USER_MODEL)
  - currency = models.CharField(max_length=3, choices=[("CAD", "Canadian Dollar")],
    default="CAD")

- Constraints and indexes:
  - migrations.AddConstraint(
      model_name="enrollmentrecord",
      constraint=models.UniqueConstraint(
        fields=("user", "product"),
        condition=Q(~Q(status__in=["cancelled", "refunded"])),
        name="uniq_user_product_active_enrollment",
      ),
    )
  - migrations.AddConstraint(
      model_name="enrollmentrecord",
      constraint=models.UniqueConstraint(
        fields=("stripe_payment_intent_id",),
        condition=Q(stripe_payment_intent_id__isnull=False),
        name="uniq_enrollment_pi",
      ),
    )
  - migrations.AddConstraint(
      model_name="enrollmentrecord",
      constraint=models.UniqueConstraint(
        fields=("stripe_checkout_session_id",),
        condition=Q(stripe_checkout_session_id__isnull=False),
        name="uniq_enrollment_cs",
      ),
    )
  - migrations.AddIndex(
      model_name="enrollmentrecord",
      index=models.Index(
        fields=["stripe_payment_intent_id"],
        name="enr_pi_idx",
        condition=Q(stripe_payment_intent_id__isnull=False),
      ),
    )
  - migrations.AddIndex(
      model_name="enrollmentrecord",
      index=models.Index(
        fields=["stripe_checkout_session_id"],
        name="enr_cs_idx",
        condition=Q(stripe_checkout_session_id__isnull=False),
      ),
    )
  - migrations.AddIndex(
      model_name="enrollmentrecord",
      index=models.Index(fields=["product", "status"],
      name="enr_product_status_idx"),
    )

- CourseProduct constraints:
  - migrations.AddConstraint(
      model_name="courseproduct",
      constraint=models.CheckConstraint(
        check=Q(pricing_type="fixed", fixed_price__gt=0) | ~Q(pricing_type="fixed"),
        name="cp_fixed_price_positive_when_fixed",
      ),
    )
  - migrations.AddConstraint(
      model_name="courseproduct",
      constraint=models.CheckConstraint(
        check=Q(min_price__gte=0) & Q(max_price__gte=F("min_price")),
        name="cp_min_le_max",
      ),
    )
  - migrations.AddConstraint(
      model_name="courseproduct",
      constraint=models.CheckConstraint(
        check=Q(pricing_type="pwyc", suggested_price__gte=F("min_price"),
        suggested_price__lte=F("max_price")) | ~Q(pricing_type="pwyc"),
        name="cp_suggested_within_range",
      ),
    )
  - migrations.AddConstraint(
      model_name="courseproduct",
      constraint=models.CheckConstraint(
        check=Q(pricing_type="free", fixed_price=0, min_price=0,
        suggested_price=0) | ~Q(pricing_type="free"),
        name="cp_free_prices_zero",
      ),
    )

### Minor nits

- Rename UniqueConstraint name from unique_user_product_enrolment to
  unique_user_product_enrollment (or the new uniq_user_product_active_enrollment).
- Consider descriptive index names for status/created_at, e.g., enr_status_created_idx
  and enr_user_status_idx (optional).
- If you keep CharField for idempotency_key, explicitly set editable=False.

Overall, main correctness issues are around deletion cascades on financial records,
Stripe id uniqueness/idempotency enforcement, and allowing re-enrollment after terminal
statuses. The proposed changes address these while improving query efficiency via partial
indexes.

---

## lms/models.py

### PR review comments

#### CourseProduct

- Validation coverage and enforcement:
  - Comment: clean() has good logical checks, but model.clean() is not guaranteed to run
    unless you call full_clean() explicitly or use ModelForms in all write paths.
  - Fix: Add DB-level CheckConstraints to enforce invariants:
    - Free => fixed_price = 0
    - Fixed => fixed_price > 0
    - PWYC => min_price <= max_price and suggested_price within [min_price, max_price]
  - Example:

```python
from django.db.models import Q, F
class Meta:
    constraints = [
        models.CheckConstraint(
            name="courseproduct_free_price_zero",
            check=Q(pricing_type="free", fixed_price=0) | ~Q(pricing_type="free"),
        ),
        models.CheckConstraint(
            name="courseproduct_fixed_price_positive",
            check=Q(pricing_type="fixed", fixed_price__gt=0) | ~Q(pricing_type="fixed"),
        ),
        models.CheckConstraint(
            name="courseproduct_pwyc_min_lte_max",
            check=Q(pricing_type="pwyc", min_price__lte=F("max_price"))
            | ~Q(pricing_type="pwyc"),
        ),
        models.CheckConstraint(
            name="courseproduct_pwyc_suggested_in_range",
            check=(
                Q(
                    pricing_type="pwyc",
                    suggested_price__gte=F("min_price"),
                    suggested_price__le=F("max_price"),
                ) | ~Q(pricing_type="pwyc")
            ),
        ),
    ]
```

- Comment: If any code writes CourseProduct directly (not via form), fixed_price==0 check
  uses int 0. Decimal comparisons work, but for clarity use Decimal("0").
  - Fix:

```python
from decimal import Decimal
if self.pricing_type == self.PricingType.FIXED and self.fixed_price == Decimal("0"):
    ...
```

- Money/currency:
  - Comment: format_price and validate_amount produce user-visible strings using decimals
    without consistent rounding. Consider quantizing to 2 decimal places to avoid
    e.g., 10.1 -> 10.10 display/intents mismatches.
  - Fix:

```python
TWO_PLACES = Decimal("0.01")

def _fmt(self, amount):
    return f"${amount.quantize(TWO_PLACES)} {self.currency}"
```

  Use _fmt in messages and format_price.

#### EnrollmentRecord

- Idempotency and race conditions:
  - Comment: unique (user, product) plus pre-check exists() is subject to race when two
    requests try to enroll concurrently; the create() can raise IntegrityError. Also,
    idempotency_key unique exists but is not used to deduplicate retries.
  - Fix: Handle both with get-or-create by idempotency_key and catching IntegrityError
    for (user, product) constraint. Also, if idempotency_key is provided and already
    exists, return existing record for idempotency semantics.
  - Suggested patch:

```python
@classmethod
@transaction.atomic
def create_for_user(cls, user, product, amount=None, idempotency_key=None):
    if not getattr(user, "is_authenticated", False):
        raise ValidationError("You must be signed in to enroll.")
    ...
    # Determine amount and validate as you have
    # Enforce course.can_user_enroll after idempotency check
    if idempotency_key:
        obj = cls.objects.filter(idempotency_key=idempotency_key).select_related(
            "product",
            "course_enrollment",
        ).first()
        if obj:
            return obj
    status = cls.Status.ACTIVE if amount == 0 else cls.Status.PENDING_PAYMENT
    try:
        enrollment = cls.objects.create(
            user=user,
            product=product,
            status=status,
            amount_paid=amount,
            idempotency_key=idempotency_key or str(uuid.uuid4()),
        )
    except IntegrityError:
        # Deduplicate by (user, product) race
        existing = cls.objects.filter(user=user, product=product).first()
        if existing:
            raise ValidationError(
                f"You already have an enrollment for this course (status: {existing.status})."
            )
        raise
    if status == cls.Status.ACTIVE:
        enrollment._create_course_enrollment()
    return enrollment
```

- Comment: idempotency_key is a CharField defaulting to uuid.uuid4. Prefer UUIDField to
  avoid implicit casts and ensure data integrity.
  - Fix:
    idempotency_key = models.UUIDField(unique=True, default=uuid.uuid4,
    help_text="Prevents duplicate enrollments")
  If you need CharField for other reasons, coerce to str on save.

- Comment: stripe_checkout_session_id and stripe_payment_intent_id are indexed but not
  unique; duplicates across records could cause issues when processing webhooks.
  Typically these should be unique when set, but allow blank.
  - Fix (Postgres):

```python
from django.db.models import Q
class Meta:
    constraints = [
        models.UniqueConstraint(
            fields=["stripe_checkout_session_id"],
            condition=~Q(stripe_checkout_session_id=""),
            name="uniq_nonblank_stripe_checkout_session_id",
        ),
        models.UniqueConstraint(
            fields=["stripe_payment_intent_id"],
            condition=~Q(stripe_payment_intent_id=""),
            name="uniq_nonblank_stripe_payment_intent_id",
        ),
    ]
```

- Authz:
  - Comment: create_for_user should enforce authentication and authorization explicitly.
    You check can_user_enroll, but that currently allows AnonymousUser to pass. See fix
    above adding is_authenticated check. Also consider checking product.course.live().public()
    if that is part of your publishing model.

- Amount semantics:
  - Comment: For paid enrollments, amount_paid is set at creation time. Usually you want
    intended_amount vs actual_captured_amount. mark_paid() does not update amount_paid
    from Stripe confirmation. If you handle it in webhooks elsewhere, fine; if not, you
    should add a method to finalize payment that sets:
    - amount_paid to the actual captured amount
    - currency check equals product.currency
    - attach stripe ids
    - then call mark_paid()
  - Fix sketch:

```python
@transaction.atomic
def finalize_payment(self, *, payment_intent_id, amount, currency, checkout_session_id=None):
    if currency != self.product.currency:
        raise ValidationError("Currency mismatch.")
    self.stripe_payment_intent_id = payment_intent_id
    if checkout_session_id:
        self.stripe_checkout_session_id = checkout_session_id
    self.amount_paid = amount
    self.save(update_fields=["stripe_payment_intent_id", "stripe_checkout_session_id", "amount_paid"])
    self.mark_paid()
```

- State machine:
  - Comment: transition_to(new_status) looks good. Consider optimistic concurrency
    control to avoid lost updates when multiple processes operate on the same record
    (e.g., webhook + UI). Simple pattern: filter(pk=self.pk, status=old_status)
    .update(status=new_status) and check rows updated == 1. If 0, reload and raise
    ValidationError about concurrent modification.

- _create_course_enrollment():
  - Comment: get_or_create is fine. If CourseEnrollment has unique constraints on
    (user, course), this is safe. Consider select_for_update on EnrollmentRecord prior
    to calling this to serialize mark_paid/mark_refunded flows and avoid duplicate
    attempts; or just rely on the one-to-one and get_or_create.

- __str__:
  - Comment: Using self.user.username assumes username field exists. With custom
    AUTH_USER_MODEL it may not. Prefer user.get_username() or str(user). Also, accessing
    self.product.course.title can trigger extra queries in admin lists.
  - Fix:

```python
def __str__(self):
    user_display = getattr(self.user, "get_username", None)
    user_display = user_display() if callable(user_display) else str(self.user)
    course_title = getattr(getattr(self.product, "course", None), "title", "Course")
    return f"{user_display} - {course_title} ({self.status})"
```

#### ExtendedCoursePage

- get_context():
  - Comment: You add checkout_* URLs. Ensure these reverse names exist in production. If
    not, reverse() will raise NoReverseMatch at page render. Consider feature-flagging
    or try/except with omission if not configured.
  - Fix example:

```python
try:
    context["checkout_success_url"] = request.build_absolute_uri(reverse("payments:checkout_success"))
    ...
except Exception:
    logger.warning("Payments URLs not configured")
    context.update({"checkout_success_url": None, "checkout_cancel_url": None, "checkout_failure_url": None})
```

- Query efficiency regressions:
  - Comment: You removed prefetch_related("categories", "tags") from CoursesIndexPage
    and related_courses. If templates access categories/tags, this will cause N+1
    queries. Unless the templates stopped using them, please restore prefetch.
  - Fix:
    In CoursesIndexPage.get_context():
    .prefetch_related("categories", "tags", "reviews")
    In related_courses:
    .public().prefetch_related["categories", "tags"](:3)

- can_user_enroll():
  - Comment: Blocks enrollment if any EnrollmentRecord exists, including cancelled/
    refunded. That is a product decision; just noting that it matches your docstring.
    Add explicit auth check to avoid AnonymousUser edge cases.
  - Fix:
    if not getattr(user, "is_authenticated", False):
        return False
  - Comment: Consider short-circuiting if product is missing. You already do a getattr
    and check. OK.
  - Comment: You might also want to check product.is_active, since create_for_user
    enforces it; aligning both reduces inconsistent behavior.
    if product and not product.is_active: return False

- get_enrollment_count():
  - Comment: Counting each time is fine; if used heavily on list views, consider
    annotating counts in the queryset to avoid per-object queries.

#### CoursesIndexPage

- Comment: See note on prefetch above; this likely causes N+1s.

#### CourseReview

- Comment: Good migration to settings.AUTH_USER_MODEL and UniqueConstraint.
- Comment: Consider adding index on (course, created_at) since ordering is by created_at
  and lookups are often course-scoped.
  - Fix:

```python
class Meta:
    indexes = [models.Index(fields=["course", "-created_at"])]
```

#### Payments/webhooks/accounting notes related to fields in this PR

- Ensure Stripe signature verification happens in webhook handlers (not shown here).
- Idempotency: With the changes suggested, make webhook upserts based on
  payment_intent_id and/or checkout_session_id (unique, non-blank), and ensure state
  transitions are idempotent. For example, if a duplicate event arrives for a succeeded
  payment, do nothing after verifying current status is ACTIVE.
- Ledger invariants: If you maintain a ledger/total elsewhere, ensure amount and currency
  are verified against product.currency and your CourseProduct.validate_amount at the
  time of capture (not just user input). Coupons/discounts should be reflected in
  amount_paid and allowed ranges for PWYC should not block discounts. Consider a
  separate intended_amount vs net_amount_paid.

#### Misc best practices

- Add default ordering to EnrollmentRecord if you display a list often (e.g., newest
  first).
- Consider db_index=True on EnrollmentRecord.product for reporting queries, though FK
  usually creates an implicit index already.
- Use select_related for common traversals in admin list views (EnrollmentRecord admin
  queryset: select_related("product", "product__course", "user")).

#### Concrete code changes summary

- Add CheckConstraints to CourseProduct as shown.
- Change EnrollmentRecord.idempotency_key to UUIDField.
- Handle idempotency and race in create_for_user as shown.
- Add unique constraints for Stripe IDs with condition ~Q(field="").
- Improve __str__ robustness for custom user models.
- Restore prefetch_related for categories/tags in CoursesIndexPage and related_courses.
- Add is_authenticated check in create_for_user and can_user_enroll.
- Optional: add finalize_payment method and optimistic concurrency in transition_to.

These changes improve correctness, avoid race conditions, ensure idempotency for payment
flows, and restore query efficiency.

---

## lms/templates/lms/includes/checkout_enroll.html

### PR review comments (inline-style) with concrete fixes

- [bug][i18n/number parsing] Numeric values in attributes must be unlocalized to avoid
  commas or locale-specific decimal separators breaking HTML number inputs and your JS
  parsing.
  - Current:
    - data-min-price="{{ product.min_price }}"
    - data-max-price="{{ product.max_price }}"
    - data-suggested-amount="{{ product.suggested_price }}"
    - min="{{ product.min_price }}"
    - max="{{ product.max_price }}"
  - Fix:
    - Load l10n filters at top: {% load l10n %}
    - Apply unlocalize to all machine-parsed numbers.
  - Suggested change (top of file):
    - {% load l10n %}
  - Suggested change (data attrs and input attrs):
    - data-min-price="{{ product.min_price|unlocalize }}"
    - data-max-price="{{ product.max_price|unlocalize }}"
    - ...
    - min="{{ product.min_price|unlocalize }}"
    - max="{{ product.max_price|unlocalize }}"
    - ...
    - data-suggested-amount="{{ product.suggested_price|unlocalize }}"

- [bug][currency] The template hardcodes a dollar sign while also printing a currency
  code, which is wrong for non-USD currencies and can double-display the currency.
  - Current:
    Suggested: ${{ product.suggested_price|floatformat:2 }} {{ product.currency }}
  - Fix options:
    - Use your existing price formatter consistently (whatever drives
      product.format_price) with currency-aware formatting.
    - Or add a currency filter/helper and use it here.
  - Suggested change (if you have a currency filter currency):
    - Suggested: {{ product.suggested_price|currency:product.currency }}
  - Or, if you already expose product.format_price for the suggested amount, prefer
    that:
    - Suggested: {{ product.formatted_suggested_price }}

- [correctness][money rounding] floatformat:2 is presentation-only and okay with Decimal,
  but ensure the backend already quantizes values to the currency's minor unit. Do not
  rely on client-provided values for any monetary logic. Server must clamp to min/max and
  quantize again.

- [DX][PWYC step size per currency] step="0.01" is incorrect for zero-decimal
  currencies (JPY) or three-decimal currencies (BHD).
  - Suggested change:
    step="{{ product.minor_unit_step|default:'0.01'|unlocalize }}"
  - Where product.minor_unit_step is a string/Decimal like "1", "0.01", or "0.001"
    derived from the currency's exponent.

- [security][CSRF] This component triggers a checkout endpoint via JS but does not
  expose a CSRF token. Ensure your JS sends X-CSRFToken or include a token in the markup
  so the client can attach it to the POST.
  - Minimal template-side fix:
    - Expose the token as a data attribute.
  - Suggested change (on the root container):
    data-csrf-token="{{ csrf_token }}"
  - And ensure your JS reads it and sets X-CSRFToken on fetch. Alternatively, render
    {% csrf_token %} as a hidden input within this container and query it.

- [security][do not trust client] Values in data- attributes (amount, min, max, product
  id) must not be trusted server-side. On the checkout_session view:
  - Re-fetch product by ID, verify is_active, verify user is allowed to enroll, and
    recompute/validate the amount entirely server-side within bounds and currency minor
    unit.
  - For free products, avoid calling Stripe altogether and handle enrollment atomically
    server-side.

- [authz] Showing the "Enroll" module based on product.is_active is fine, but ensure
  server-side authorization is enforced in payments:checkout_session. For example, if
  the course is restricted or the user lacks access, the view must reject the request
  even if the template is shown.

- [a11y] The error banner should be announced to assistive tech.
  - Current:
    <div class="hidden ... " data-checkout-error>Something went wrong...</div>
  - Suggested change:
    <div class="hidden ... " data-checkout-error role="alert" aria-live="polite">...</div>

- [a11y/UX] Consider a loading/disabled state and aria-busy on the button while
  submitting to prevent double-submits and clarify state. Your JS likely toggles this;
  reserve hooks in markup now.
  - Suggested change (button):
    <button ... data-checkout-submit aria-live="polite" aria-busy="false"
    data-loading-text="Processing...">

- [consistency] Use the same formatter for all price displays. You use
  product.format_price for the headline, but not for suggested/min/max text. Consider:
  - Human-readable: format with currency-aware formatter.
  - Machine-readable (attributes): unlocalized decimals only.

- [copy] Terms link can be more descriptive for screen readers. Consider:
  By enrolling, you agree to our <a ... aria-label="Read our terms and conditions">terms</a>.

- [minor] If product.pricing_type == "free", the button text is "Enroll for Free" but
  still points to payments:checkout_session. Ensure backend fast-paths free enrollments
  without touching Stripe, and that the operation is idempotent.

- [Stripe/payments invariants] Not in this file, but since this initiates payments:
  - checkout_session view must:
    - Validate CSRF, authz, product is_active, and ownership/eligibility.
    - Recompute amount server-side, clamp to min/max, enforce currency exponent, and
      raise on currency mismatch.
    - Create idempotent payment intents/sessions (idempotency key per user+product+intent).
    - For success/cancel/failure URLs, do not trust client-supplied values; derive from
      server or whitelist.
  - Webhook handler must:
    - Verify Stripe signature.
    - Enforce idempotency for events.
    - Maintain ledger totals and invariants within transaction.atomic and SELECT ...
      FOR UPDATE as needed.
    - Only mark enrollment on terminal events (e.g., payment_succeeded) after checking
      amounts/currency match expected.

### Concrete patched snippet (minimal, safe changes)

```django
{% load l10n %}
{% if product and product.is_active %}
    <div class="bg-white border border-neutral-200 rounded-lg p-6 shadow-sm"
         data-checkout-form
         data-checkout-url="{% url 'payments:checkout_session' %}"
         data-product-id="{{ product.id }}"
         data-success-url="{{ checkout_success_url }}"
         data-cancel-url="{{ checkout_cancel_url }}"
         data-failure-url="{{ checkout_failure_url }}"
         data-pricing-type="{{ product.pricing_type }}"
         data-min-price="{{ product.min_price|unlocalize }}"
         data-max-price="{{ product.max_price|unlocalize }}"
         data-csrf-token="{{ csrf_token }}">
        <div class="flex flex-col gap-4">
            <div class="flex items-center justify-between gap-4">
                <div>
                    <p class="text-sm uppercase tracking-wide text-neutral-500">Course Price</p>
                    <p class="text-2xl font-semibold text-primary-900">{{ product.format_price }}</p>
                    {% if product.pricing_type == "pwyc" %}
                        <p class="text-sm text-neutral-600">
                            Suggested: {{ product.suggested_price|floatformat:2 }} {{ product.currency }}
                            {# Replace with your currency-aware formatter if available #}
                        </p>
                    {% endif %}
                </div>
                <div class="rounded-full bg-primary-50 px-3 py-1 text-xs font-semibold text-primary-700">
                    Secure checkout
                </div>
            </div>

            {% if product.pricing_type == "pwyc" %}
                <label class="block">
                    <span class="text-sm font-medium text-neutral-700">Choose your price</span>
                    <div class="mt-2 flex flex-col sm:flex-row gap-3">
                        <div class="relative flex-1">
                            <span class="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-500">$</span>
                            <input type="number"
                                   min="{{ product.min_price|unlocalize }}"
                                   max="{{ product.max_price|unlocalize }}"
                                   step="{{ product.minor_unit_step|default:'0.01'|unlocalize }}"
                                   placeholder="{{ product.suggested_price|floatformat:2 }}"
                                   data-checkout-amount
                                   class="w-full rounded-md border border-neutral-300 pl-7 pr-3 py-2 text-neutral-900 focus:border-primary-500 focus:ring-primary-500">
                        </div>
                        <button type="button"
                                class="inline-flex items-center justify-center rounded-md border border-neutral-300 bg-neutral-50 px-4 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-100"
                                data-checkout-suggested
                                data-suggested-amount="{{ product.suggested_price|unlocalize }}">
                            Use suggested
                        </button>
                    </div>
                    <p class="mt-2 text-xs text-neutral-500">
                        Minimum {{ product.min_price|floatformat:2 }} {{ product.currency }}
                        / Maximum {{ product.max_price|floatformat:2 }} {{ product.currency }}
                        {# Prefer currency-aware formatting here too #}
                    </p>
                </label>
            {% endif %}

            <div class="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
                <button type="button"
                        data-checkout-submit
                        aria-live="polite"
                        aria-busy="false"
                        class="inline-flex items-center justify-center px-6 py-3 rounded-md text-white bg-cyan-600 hover:bg-cyan-700 font-medium shadow-sm transition-colors duration-200">
                    <span data-checkout-button-text>
                        {% if product.pricing_type == "free" %}
                            Enroll for Free
                        {% elif product.pricing_type == "fixed" %}
                            Enroll Now
                        {% else %}
                            Continue to Payment
                        {% endif %}
                    </span>
                </button>
                <p class="text-xs text-neutral-500">
                    By enrolling, you agree to our
                    <a href="{% url 'terms_and_conditions' %}" class="text-cyan-700 hover:text-cyan-800" aria-label="Read our terms and conditions">terms</a>.
                </p>
            </div>

            <div class="hidden rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700"
                 data-checkout-error
                 role="alert"
                 aria-live="polite">
                Something went wrong. Please try again.
            </div>
        </div>
    </div>
{% else %}
    <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
        <p class="text-yellow-800">
            Enrollment is currently unavailable for this course. Please check back later.
        </p>
    </div>
{% endif %}
```

### Notes for the backend (outside this template)

- Ensure checkout_session is POST-only, CSRF-protected, and requires appropriate auth
  or captures anonymous sessions intentionally.
- Validate success/cancel/failure URLs server-side (do not accept arbitrary redirects).
- For free enrollments, wrap enrollment creation in transaction.atomic and make it
  idempotent per user+product to avoid duplicate enrollments on retries.
- Stripe/webhooks: verify signatures, enforce idempotency keys, and maintain
  ledger/enrollment invariants before marking success.

---

## lms/tests.py

### PR review comments

#### General

- Tests add valuable coverage for pricing, enrollment lifecycle, and page context. A few
  areas need adjustment to reflect robust payments/idempotency semantics, and some tests
  are brittle due to hard-coded strings and currency codes.
- Consider consistency: use enum constants (e.g., CourseProduct.PricingType.FIXED)
  everywhere instead of raw strings ("fixed", "pwyc"). This reduces typo risk and
  improves readability.
- Remove unused imports (Mock).
- Several tests implicitly rely on side effects that should be driven by a single path
  (e.g., activation via mark_paid). Align tests so they enforce the correct invariant
  rather than permitting ambiguous code paths.

#### Payments + idempotency

- Critical: test_create_for_user_idempotency_key_unique currently expects an
  IntegrityError when a duplicate idempotency_key is used. For payment workflows,
  idempotency should:
  - return the existing record when params match (true idempotency), and
  - raise a ValidationError with a clear message/code (idempotency_conflict) when the
    same key is reused with different parameters, instead of surfacing an IntegrityError
    from the DB.
- Concrete test fix:
  - Split into two tests reflecting both behaviors.
  - Replace IntegrityError assertions with deterministic idempotency behavior checks.

### Suggested changes

1) Remove unused imports.

- Top of file:
  - Remove: from unittest.mock import Mock as it is no longer used.

1) Prefer enum constants over raw strings for pricing_type.

- Across CourseProductTest and EnrollmentRecordTest, replace "fixed", "pwyc", "free"
  with CourseProduct.PricingType.FIXED, CourseProduct.PricingType.PWYC,
  CourseProduct.PricingType.FREE.

Example:

- Before:
  product = CourseProduct.objects.create(course=self.course, pricing_type="fixed",
  fixed_price=Decimal("99.99"))
- After:
  product = CourseProduct.objects.create(course=self.course,
  pricing_type=CourseProduct.PricingType.FIXED, fixed_price=Decimal("99.99"))

1) Hard-coded currency in tests is brittle.

- format_price assertions check "$... CAD". If currency is configurable, these tests
  will break. Prefer asserting numeric formatting and that a currency code suffix
  exists, or derive expected from settings or product.currency. For example, assert
  "49.99" in product.format_price() and "CAD" in product.format_price() to allow
  runtime configurability.

1) Idempotency test rewrite (critical).

- Replace test_create_for_user_idempotency_key_unique with two tests:

a) Same payload returns existing (true idempotency):

```python
def test_create_for_user_idempotency_same_payload_returns_existing(self):
    idempotency_key = "duplicate-key"
    enrollment1 = EnrollmentRecord.create_for_user(
        user=self.user,
        product=self.product,
        amount=Decimal("99.99"),
        idempotency_key=idempotency_key,
    )
    # Reusing same key with same exact payload returns the same record
    enrollment2 = EnrollmentRecord.create_for_user(
        user=self.user,
        product=self.product,
        amount=Decimal("99.99"),
        idempotency_key=idempotency_key,
    )
    self.assertEqual(enrollment1.id, enrollment2.id)
    self.assertEqual(enrollment2.amount_paid, Decimal("99.99"))
    self.assertEqual(enrollment2.product_id, self.product.id)
```

b) Conflicting payload raises a ValidationError (not IntegrityError):

```python
def test_create_for_user_idempotency_conflict_raises(self):
    idempotency_key = "duplicate-key"
    EnrollmentRecord.create_for_user(
        user=self.user,
        product=self.product,
        amount=Decimal("99.99"),
        idempotency_key=idempotency_key,
    )
    other_course = ExtendedCoursePage(
        title="Other Course",
        slug="other-course",
        difficulty="beginner",
        is_published=True,
    )
    self.courses_index.add_child(instance=other_course)
    other_course.save_revision().publish()
    other_product = CourseProduct.objects.create(
        course=other_course,
        pricing_type=CourseProduct.PricingType.FIXED,
        fixed_price=Decimal("20.00"),
    )
    # Reusing same key with different payload should raise a ValidationError with a clear message/code.
    with self.assertRaises(ValidationError) as cm:
        EnrollmentRecord.create_for_user(
            user=self.user,
            product=other_product,
            amount=Decimal("20.00"),
            idempotency_key=idempotency_key,
        )
    self.assertIn("idempotency", str(cm.exception).lower())
```

Rationale:

- This guides the model implementation toward correct idempotency semantics (no reliance
  on DB IntegrityError).
- It aligns with robust payment processing practices.

1) Activation path: enforce side effects only via mark_paid, or assert course_enrollment
   creation when transitioning to ACTIVE.

- In test_transition_to_all_valid_transitions, you transition PENDING_PAYMENT -> ACTIVE
  via transition_to without asserting that CourseEnrollment is created. If your domain
  requires that activation always creates CourseEnrollment, either:
  - call mark_paid (recommended single path for activation side effects), or
  - assert that course_enrollment is created when using transition_to(STATUS.ACTIVE),
    ensuring implementation does the right thing.

Concrete change (prefer mark_paid to centralize side effects):

```python
# PENDING_PAYMENT -> ACTIVE
enrollment1 = EnrollmentRecord.create_for_user(
    user=self.user, product=self.product, amount=Decimal("99.99")
)
enrollment1.mark_paid()
self.assertEqual(enrollment1.status, EnrollmentRecord.Status.ACTIVE)
self.assertIsNotNone(enrollment1.course_enrollment)
```

If you keep transition_to(STATUS.ACTIVE), add:

```python
self.assertIsNotNone(enrollment1.course_enrollment)
```

1) Login CTA next parameter robustness.

- test_login_cta_next_points_to_course_page:
  - Consider URL-encoding the next parameter in expectations to avoid future issues if
    course URLs include querystrings or non-ASCII.
  - Example:

```python
from urllib.parse import quote
expected_next = quote(self.course.url, safe="")
self.assertIn(f"{login_url}?next={expected_next}", content)
self.assertIn(f"{signup_url}?next={expected_next}", content)
```

1) Context URL assertions should use reverse.

- test_get_context_logged_in_user:
  - Instead of asserting substrings like "/payments/checkout/success/", resolve named
    routes (if available) and assert equality or inclusion. Example:

```python
self.assertEqual(context["checkout_success_url"], reverse("payments:checkout_success"))
self.assertEqual(context["checkout_cancel_url"], reverse("payments:checkout_cancel"))
self.assertEqual(context["checkout_failure_url"], reverse("payments:checkout_failure"))
```

  If the code builds absolute URIs, compare path components or parse with urlparse.

1) Ensure Site setup is consistent across tests that rely on serving.

- ExtendedCoursePageTest setUp correctly ensures a default Site is configured. Good.
- CourseProductTest and EnrollmentRecordTest do not use self.client or self.course.url;
  if you later add serving checks to those tests, you will need similar Site setup.

1) Message assertions should prefer codes where available.

- Where asserting on ValidationError, prefer checking exception.message_dict keys or
  exception.error_list with .code if your exceptions set codes. This makes tests
  resilient to phrasing changes.

1) Minor: repr tests are brittle.

- test_product_repr_representation asserts exact Decimal repr and field labels. This can
  be brittle if repr changes. Consider asserting presence of core identifiers (class
  name, id, pricing_type) and avoid exact Decimal string matching.

1) Enrollment limit and prerequisites race conditions (follow-up for model code, not
    this test).

- Tests validate behavior but the underlying implementation should be transactionally
  safe:
  - Wrap EnrollmentRecord.create_for_user in transaction.atomic and re-check
    prerequisites/enrollment_limit within the transaction.
  - Use select_for_update on rows (e.g., the course row or a counter) or enforce an
    application-level check that cannot be bypassed by race conditions. Otherwise,
    concurrent requests can oversubscribe beyond enrollment_limit.
  - Ensure mark_paid is also wrapped in transaction.atomic and uses get_or_create for
    CourseEnrollment to achieve idempotency under concurrency.

1) Refund/cancel terminal states and side effects (follow-up for model code).

- Your tests correctly treat REFUNDED and CANCELLED as terminal. Ensure application code:
  - Revokes course access on REFUNDED/CANCELLED (e.g., delete/mark inactive
    CourseEnrollment) and that transitions are guarded accordingly.
  - mark_paid must be a no-op for REFUNDED/CANCELLED and raise a clear ValidationError
    (your test checks message includes "cancelled/refunded" - good).

### Summary of test file concrete edits

- Remove unused import:
  - Delete: from unittest.mock import Mock

- Replace raw pricing_type strings with enum constants across tests.

- Update idempotency tests:
  - Replace test_create_for_user_idempotency_key_unique with two tests shown in (4).

- Update transition to ACTIVE test for side effect:
  - In test_transition_to_all_valid_transitions, call mark_paid for the ACTIVE
    transition and assert course_enrollment is created (or add assertion if you keep
    transition_to).

- Optional robustness improvements:
  - Encode next parameter in test_login_cta_next_points_to_course_page.
  - Use reverse for checkout URLs in test_get_context_logged_in_user.

### Notes for the model implementation (to pass and harden these tests)

- EnrollmentRecord.create_for_user:
  - Wrap in transaction.atomic.
  - Enforce unique idempotency_key at the DB level, but catch IntegrityError to implement
    idempotency semantics: if a record with that id exists and the payload matches,
    return it; if it conflicts, raise ValidationError with code "idempotency_conflict".
  - Validate prerequisites and enrollment_limit inside the atomic block.
  - Use select_for_update on any relevant rows or implement a capped counter to avoid
    race conditions.
- EnrollmentRecord.mark_paid:
  - Wrap in transaction.atomic.
  - Ensure idempotency with get_or_create on CourseEnrollment and a unique constraint
    on (user, course).
  - Guard against terminal statuses.

These changes will make your payment/enrollment flows correct under concurrency and
aligned with best practices for idempotency and side effects.

---

## payments/admin.py

### PR review comments (inline)

- PaymentLedgerEntryInline: Make ledger entries strictly read-only in admin.
  - Right now readonly_fields and can_delete=False are good, but staff can still click
    through because show_change_link=True, and they might be able to add entries
    depending on permissions.
  - Suggest:
    - show_change_link=False to avoid navigation to a change form.
    - has_add_permission returns False to prevent manual creation.
    - has_change_permission returns False to enforce read-only.
    - ordering = ("created_at",) for deterministic display.

- RefundStateFilter.queryset: Handle NULL amounts to avoid incorrect classification or
  database errors.
  - If amount_refunded or amount_gross can be NULL (often the case early in processing),
    your comparisons may misclassify or skip records. Use Coalesce to treat NULL as 0.
  - Also, keeping the exclude(amount_gross=0) in full makes sense; mirror that via the
    annotated field.

- PaymentAdmin: Lock down financial records and improve query efficiency.
  - Security/invariants:
    - Consider making Payment effectively read-only in admin to protect ledger/totals
      invariants and prevent accidental edits that desync Stripe vs internal state.
    - At minimum, mark Stripe identifiers and status as readonly_fields and disallow
      add/delete. Ideally, restrict change to superusers only.
  - Query efficiency:
    - Add list_select_related for enrollment_record and related product/course to avoid
      N+1 on list_display and filters.
    - Use raw_id_fields for enrollment_record to avoid loading huge dropdowns.
  - Search:
    - Use exact matching for Stripe IDs to avoid slow icontains lookups and ensure
      precise results (prefix fields with "=" in search_fields).
  - Admin UX:
    - Add ordering, date_hierarchy, and list_per_page for better navigation.

- WebhookEventAdmin: Treat as immutable audit log.
  - For idempotency and auditability, this model should be read-only with no add/change/
    delete in admin. Right now only processed_at is readonly; staff could alter
    event_type/success which is risky.
  - Make all fields readonly and disallow add/change/delete.
  - Use exact search on stripe_event_id, add ordering and date_hierarchy.

- General Stripe/webhooks/accounting notes (contextual):
  - Ensuring Payment and WebhookEvent are immutable in admin helps preserve the
    canonical audit trail, supports idempotency checks (e.g., deduplicating by
    stripe_event_id), and prevents divergence from ledger/totals computed elsewhere.

### Proposed patch

```python
from django.contrib import admin
from django.db.models import F
from django.db.models.functions import Coalesce

from payments.models import Payment, PaymentLedgerEntry, WebhookEvent


class PaymentLedgerEntryInline(admin.TabularInline):
    model = PaymentLedgerEntry
    extra = 0
    fields = (
        "entry_type",
        "amount",
        "currency",
        "net_amount",
        "stripe_charge_id",
        "stripe_refund_id",
        "stripe_balance_transaction_id",
        "processed_at",
        "created_at",
    )
    readonly_fields = fields
    show_change_link = False
    can_delete = False
    ordering = ("created_at",)

    def has_add_permission(self, request, obj=None):
        # Ledger must be append-only via code paths, not admin.
        return False

    def has_change_permission(self, request, obj=None):
        # Enforce read-only inline
        return False


class RefundStateFilter(admin.SimpleListFilter):
    title = "refund state"
    parameter_name = "refund_state"

    def lookups(self, request, model_admin):
        return [
            ("none", "No refunds"),
            ("partial", "Partial refunds"),
            ("full", "Full refunds"),
        ]

    def queryset(self, request, queryset):
        # Treat NULL amounts as zero to avoid misclassification
        qs = queryset.annotate(
            refunded=Coalesce(F("amount_refunded"), 0),
            gross=Coalesce(F("amount_gross"), 0),
        )
        if self.value() == "none":
            return qs.filter(refunded=0)
        if self.value() == "partial":
            return qs.filter(refunded__gt=0, refunded__lt=F("gross"))
        if self.value() == "full":
            return qs.filter(refunded__gte=F("gross")).exclude(gross=0)
        return queryset


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "enrollment_record",
        "amount",
        "amount_gross",
        "amount_refunded",
        "amount_net",
        "currency",
        "status",
        "created_at",
    )
    list_filter = (
        "status",
        RefundStateFilter,
        "currency",
        "enrollment_record__product",
        "enrollment_record__product__course",
        "created_at",
    )
    search_fields = (
        "enrollment_record__user__username",
        "enrollment_record__product__course__title",
        "=stripe_checkout_session_id",
        "=stripe_payment_intent_id",
        "=stripe_charge_id",
    )
    readonly_fields = (
        "amount_gross",
        "amount_refunded",
        "amount_net",
        "created_at",
        "updated_at",
        # Protect Stripe linkage and status from manual edits
        "stripe_checkout_session_id",
        "stripe_payment_intent_id",
        "stripe_charge_id",
        "status",
        "currency",
    )
    inlines = [PaymentLedgerEntryInline]
    list_select_related = (
        "enrollment_record",
        "enrollment_record__product",
        "enrollment_record__product__course",
    )
    raw_id_fields = ("enrollment_record",)
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_per_page = 50

    def has_add_permission(self, request):
        # Payments must be created by application logic/Stripe flows
        return False

    def has_delete_permission(self, request, obj=None):
        # Preserve audit trail; do not allow deletion
        return False

    def has_change_permission(self, request, obj=None):
        # Only superusers may modify; ideally nobody should.
        return request.user.is_superuser

    # If you want staff to view (but not change) without being superusers
    # and your project uses view permissions, you can optionally add:
    # def has_view_permission(self, request, obj=None):
    #     return True


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("stripe_event_id", "event_type", "success", "processed_at")
    list_filter = ("event_type", "success", "processed_at")
    search_fields = ("=stripe_event_id",)
    readonly_fields = ("processed_at",)
    date_hierarchy = "processed_at"
    ordering = ("-processed_at",)

    def get_readonly_fields(self, request, obj=None):
        # Make all fields read-only to preserve idempotency/audit trail
        opts = self.model._meta
        all_field_names = [f.name for f in opts.concrete_fields] + [m.name for m in opts.many_to_many]
        return tuple(set(all_field_names + list(super().get_readonly_fields(request, obj))))

    def has_add_permission(self, request):
        # Events should only be created by webhook ingestion
        return False

    def has_change_permission(self, request, obj=None):
        # Events should be immutable
        return False

    def has_delete_permission(self, request, obj=None):
        # Prevent removal of audit log
        return False
```

Notes:

- If EnrollmentRecord admin is configured for autocomplete, you can switch raw_id_fields
  to autocomplete_fields = ("enrollment_record",).
- If amount_refunded/amount_gross are guaranteed non-null integers in your schema, the
  Coalesce annotation is not strictly necessary; keeping it is defensive and harmless.

---

## payments/migrations/0001_initial.py

### PR review

#### High-level

- Overall structure is fine for an initial migration, but we are missing a few critical
  invariants for payments/webhooks:
  - Enforce idempotency on Stripe identifiers (payment_intent, checkout_session) with
    unique constraints.
  - Preserve accounting audit trail: avoid cascading deletion of Payment when its
    EnrollmentRecord is deleted.
  - Add constraints to prevent invalid amounts and ensure at least one Stripe reference
    is present.
  - WebhookEvent should not default to success before processing; also separate
    received_at vs processed_at timestamps.
  - Consider linking Payment.last_event to a WebhookEvent FK or at least index it for
    idempotent processing checks.

#### Inline comments

- payments/migrations/0001_initial.py:13
  - dependencies looks fine.

- payments/migrations/0001_initial.py:19-33 (WebhookEvent model)
  - The field name processed_at with auto_now_add=True suggests "received time" rather
    than "processed time." Today it always equals the creation time. Please:
    - Rename to received_at with auto_now_add=True.
    - Add processed_at = DateTimeField(null=True, blank=True) to record actual
      processing completion time.
  - success defaulting to True is dangerous. Until we have verified signature and
    processed successfully, it should be False (or better, a tri-state).
    - Rename to processed_success = BooleanField(default=False).
  - Consider storing the Stripe-Signature header and request_id for audit/debugging:
    - signature = CharField(max_length=512, blank=True)
    - request_id = CharField(max_length=255, blank=True)  # Stripe-Request-Id
  - error_message should allow null to differentiate "not set" from "set but empty":
    - error_message = TextField(blank=True, null=True)
  - Indexes: you have an index on (event_type, processed_at). If we rename to
    received_at + add processed_at, keep:
    - Index on (event_type, received_at)
    - Optional index on processed_success for ops dashboards
  - raw_event_data JSON is okay, but ensure we are not storing PII we do not need.
    No change needed in migration, but note for data retention.

- payments/migrations/0001_initial.py:35-51 (Payment model)
  - Accounting/audit: on_delete=CASCADE can destroy payment rows if the enrollment is
    removed. We should PROTECT instead to keep the ledger immutable.
  - Amount: add a check constraint to ensure non-negative amounts. Also consider
    storing integer minor units (e.g., cents) to avoid rounding; if staying with
    Decimal(10,2), at least enforce >= 0.
  - Currency: max_length=10 is unnecessarily large; ISO-4217 codes are 3 chars. Also
    consider choices or a validator to enforce uppercase 3 letters.
  - Stripe identifiers:
    - stripe_payment_intent_id and stripe_checkout_session_id should be unique for
      idempotency. Right now they are indexed only, allowing duplicates.
    - Make them nullable (null=True, blank=True) and add conditional UniqueConstraint
      so multiple NULLs are allowed.
  - Ensure at least one of stripe_payment_intent_id or stripe_checkout_session_id is
    present:
    - Add CheckConstraint with OR on non-null of either.
  - stripe_event_id on Payment (last event applied):
    - Add db_index=True to speed idempotency checks during event application.
    - Consider making this a nullable FK to WebhookEvent to guarantee referential
      integrity; if you prefer to keep it as a char field, at least index it.
  - Status/ordering/indexing looks good. You already have an index on (status,
    created_at).

### Concrete migration fixes (replace/amend this initial migration; if this is already

applied in environments, create a new migration that performs equivalent operations)

```python
from django.db.models import Q
from django.core.validators import MinValueValidator

class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("lms", "0003_courseproduct_enrollmentrecord_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="WebhookEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("stripe_event_id", models.CharField(db_index=True, max_length=255, unique=True)),
                ("event_type", models.CharField(max_length=100)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("processed_at", models.DateTimeField(null=True, blank=True)),
                ("processed_success", models.BooleanField(default=False)),
                ("signature", models.CharField(max_length=512, blank=True)),
                ("request_id", models.CharField(max_length=255, blank=True)),
                ("raw_event_data", models.JSONField()),
                ("error_message", models.TextField(blank=True, null=True)),
            ],
            options={
                "ordering": ["-received_at"],
                "indexes": [
                    models.Index(fields=["event_type", "received_at"], name="payments_we_event_t_received_idx"),
                    models.Index(fields=["processed_success", "received_at"], name="payments_we_success_received_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10, validators=[MinValueValidator(0)])),
                ("currency", models.CharField(default="CAD", max_length=3)),
                ("status", models.CharField(choices=[("initiated", "Initiated"), ("processing", "Processing"), ("succeeded", "Succeeded"), ("failed", "Failed"), ("refunded", "Refunded")], default="initiated", max_length=20)),
                ("stripe_checkout_session_id", models.CharField(null=True, blank=True, db_index=True, max_length=255)),
                ("stripe_payment_intent_id", models.CharField(null=True, blank=True, db_index=True, max_length=255)),
                ("failure_reason", models.TextField(blank=True)),
                ("stripe_event_id", models.CharField(blank=True, db_index=True, help_text="Last Stripe event that updated this payment", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("enrollment_record", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="lms.enrollmentrecord")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["status", "created_at"], name="payments_pa_status_created_idx"),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.UniqueConstraint(
                condition=Q(stripe_payment_intent_id__isnull=False),
                fields=("stripe_payment_intent_id",),
                name="uniq_payment_intent"
            ),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.UniqueConstraint(
                condition=Q(stripe_checkout_session_id__isnull=False),
                fields=("stripe_checkout_session_id",),
                name="uniq_checkout_session"
            ),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.CheckConstraint(
                check=Q(amount__gte=0),
                name="payment_amount_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.CheckConstraint(
                check=Q(stripe_payment_intent_id__isnull=False) | Q(stripe_checkout_session_id__isnull=False),
                name="payment_has_stripe_ref",
            ),
        ),
    ]
```

### Notes/justification

- Idempotency: UniqueConstraint on Stripe IDs ensures we cannot create duplicate Payment
  records for the same Stripe object and enables safe upserts in webhook handlers.
  Conditional unique avoids issues with multiple NULLs and keeps portability.
- WebhookEvent lifecycle: Default processed_success=False prevents false positives;
  received_at vs processed_at captures actual processing time and helps recover/retry
  logic and monitoring.
- Audit/ledger: PROTECT on FK prevents paid records from disappearing if upstream
  enrollment is deleted. This is a common accounting requirement.
- Performance: Indexes on Stripe IDs and event_id enable O(1) lookups in webhook
  processing. The composite index on (status, created_at) is fine for back-office lists.
- Data quality: amount >= 0 and currency length 3 avoid bad rows. If you anticipate
  zero-decimal or three-decimal currencies, consider storing amounts as integer minor
  units (e.g., amount_cents = BigIntegerField) instead of Decimal(10,2).

### Optional follow-ups (non-blocking)

- Make Payment.stripe_event_id a nullable FK to WebhookEvent with on_delete=SET_NULL to
  enforce referential integrity.
- Add a validator to currency to enforce uppercase 3-letter ISO codes.
- If you plan to process events idempotently per Payment as well, consider an additional
  UniqueConstraint on (enrollment_record, stripe_payment_intent_id) to guard against
  cross-enrollment mix-ups.
- Evaluate whether you need raw request headers on WebhookEvent for debugging signature
  verification issues.

### Webhook handling notes

- Verify Stripe signature using the endpoint secret before inserting WebhookEvent.
- Wrap processing in transaction.atomic and use the WebhookEvent unique stripe_event_id
  to ensure idempotent processing.
- Maintain invariants: payments totals/ledger updates must be balanced and only once per
  event; use select_for_update on Payment row during webhook handling to prevent
  concurrent updates.

---

## payments/migrations/0002_accounting_ledger.py

### Review comments

- Blocking: Adding non-null CharFields to existing Payment with no default will fail on
  existing rows.
  - Context: These new Payment fields are non-nullable and have no default:
    - stripe_balance_transaction_id = models.CharField(blank=True, db_index=True,
      max_length=255)
    - stripe_charge_id = models.CharField(blank=True, db_index=True, max_length=255)
  - Issue: On PostgreSQL (and most backends), adding a NOT NULL column without a default
    will fail if the table has existing rows because existing rows would get NULL.
  - Fix: Set default="" (empty string) for these CharFields in the migration (and in the
    model), or make them null=True initially and backfill, then tighten to null=False
    with a follow-up migration. Given you already use blank=True and rely on empty
    string semantics elsewhere, default="" is consistent.
  - Suggested change:
    - payment.stripe_balance_transaction_id: add default=""
    - payment.stripe_charge_id: add default=""

- Blocking/Correctness: Conditional UniqueConstraint uses private _negated argument on Q
  - Context:
    - You have:
      models.UniqueConstraint(
        condition=models.Q(("entry_type", "charge"), models.Q(("stripe_charge_id", ""),_negated=True)),
        fields=("entry_type", "stripe_charge_id"),
        name="unique_charge_entry_per_charge_id",
      )
  - Issue: Passing _negated=True to Q() is using a private API and is brittle. Prefer
    the public ~Q(...) operator. Also, tuple-based Q construction is harder to read;
    use keyword args.
  - Fix:
    - Use: condition=models.Q(entry_type="charge") & ~models.Q(stripe_charge_id="")
    - Same for the refund constraint.

- Idempotency: Missing uniqueness guard on ledger stripe_balance_transaction_id
  - Context: A Stripe balance_transaction ID is globally unique per Stripe object.
    Webhooks can be delivered multiple times.
  - Issue: You guard charge and refund duplication, but not fee or general balance
    transactions. A duplicate webhook could create duplicate fee ledger entries.
  - Fix: Add a conditional unique constraint on stripe_balance_transaction_id when it is
    not empty, across all entry types.
  - Suggested:
    - models.UniqueConstraint(
        condition=~models.Q(stripe_balance_transaction_id=""),
        fields=("stripe_balance_transaction_id",),
        name="unique_ledger_per_balance_txn"
      )

- Idempotency/Consistency: Consider uniqueness on Payment.stripe_charge_id and
  Payment.stripe_balance_transaction_id
  - Context: Payment now stores Stripe IDs and both are indexed.
  - Issue: Without a uniqueness constraint, duplicate Payment rows could point to the
    same Stripe object.
  - Fix: Add conditional unique constraints that ignore empty strings:
    - models.UniqueConstraint(
        condition=~models.Q(stripe_charge_id=""),
        fields=("stripe_charge_id",),
        name="unique_payment_stripe_charge_id"
      )
    - models.UniqueConstraint(
        condition=~models.Q(stripe_balance_transaction_id=""),
        fields=("stripe_balance_transaction_id",),
        name="unique_payment_stripe_balance_txn_id"
      )

- Data integrity: Monetary fields handling and constraints
  - Context: You introduced amount_gross, amount_net, amount_refunded as Decimal(10,2)
    with default=0.
  - Issues and suggestions:
    - Precision: max_digits=10, decimal_places=2 may be too tight long-term (e.g.,
      aggregates, high-value charges). Stripe uses integer minor units; consider
      storing minor units as BigInteger or increase to max_digits=12-14.
    - Defaults: Using default=0 is acceptable, but ensure the model defaults use
      Decimal("0.00") to avoid float semantics at the Python level.
    - Integrity: Add DB-level CheckConstraints:
      - Non-negative amounts for payment columns.
      - amount_refunded <= amount_gross.
    - Example constraints on Payment:
      - models.CheckConstraint(name="payment_amounts_non_negative",
        check=models.Q(amount_gross__gte=0, amount_net__gte=0, amount_refunded__gte=0))
      - models.CheckConstraint(name="payment_refunded_lte_gross",
        check=models.Q(amount_refunded__lte=models.F("amount_gross")))
    - Ledger sign conventions: Decide whether amount is always positive and semantics
      are derived from entry_type. If so, add CheckConstraint(amount__gte=0). If refunds
      should be stored as negative amounts, add per-type sign checks. Right now there is
      no constraint, so mistakes can slip in.

- Currency consistency
  - Context: PaymentLedgerEntry.currency defaults to "CAD". Payment likely already has
    a currency field.
  - Issue: Ledger entry currency can diverge from the parent Payment. This will break
    accounting invariants.
  - Fix options:
    - If Payment has a currency, drop currency from ledger entries and derive from
      Payment at read-time, or
    - Mirror Payment currency into ledger currency and enforce in application code.
      DB-level enforcement across tables is not feasible with a CheckConstraint; if on
      Postgres and you must enforce at DB-level, you would need a trigger, which is
      overkill in most apps.
    - At minimum, set default to Payment's currency in the model save logic, not a
      hard-coded "CAD".

- Query efficiency: Indexes
  - Good: Index on (entry_type, processed_at).
  - Missing: Common access patterns are "ledger entries for a payment ordered by
    processed_at".
  - Fix: Add an index on ("payment", "processed_at") and possibly on "payment" alone
    (the composite covers that in Postgres).
    - models.Index(fields=["payment", "processed_at"], name="ledger_by_payment_processed_at")

- Defaults on CharFields in PaymentLedgerEntry
  - Context: stripe_charge_id, stripe_refund_id, stripe_balance_transaction_id are
    CharFields with blank=True and no default.
  - Issue: Although creating a new table with NOT NULL and no default is fine, new
    ORM-created rows will try to insert NULL unless the code sets empty strings
    explicitly.
  - Fix: Add default="" to each of these fields for consistency with blank=True and
    your conditional uniqueness constraints.

- Migration performance/locking
  - Context: Adding three non-null Decimal columns with default=0 to a large payments
    table can rewrite/lock the table on Postgres.
  - Suggestion: If the table is large, consider a safer, multi-step migration:
    - Add columns as null=True, no default.
    - RunPython to backfill in batches.
    - Add CheckConstraints/NOT NULL and set model-level defaults in a follow-up
      migration.

### Concrete suggested patch (edited migration)

Replace the relevant parts in operations with the following adjusted operations and
options. Note: This assumes you haven't applied this migration yet. If you have, create
a new migration that adds constraints and alters defaults instead.

- Adjust AddField on Payment
  - stripe_charge_id and stripe_balance_transaction_id should include default="".

- CreateModel PaymentLedgerEntry
  - Add default="" to the stripe_* CharFields.
  - Replace Q conditions using ~ and keyword args.
  - Add unique constraint for balance_transaction_id.
  - Add index on (payment, processed_at).

- Add constraints to Payment for amounts and uniqueness on Stripe IDs.

Example edit:

```python
migrations.AddField(
    model_name="payment",
    name="stripe_balance_transaction_id",
    field=models.CharField(blank=True, default="", db_index=True, max_length=255),
),
migrations.AddField(
    model_name="payment",
    name="stripe_charge_id",
    field=models.CharField(blank=True, default="", db_index=True, max_length=255),
),

migrations.CreateModel(
    name="PaymentLedgerEntry",
    fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("entry_type", models.CharField(choices=[("charge", "Charge"), ("refund", "Refund"), ("adjustment", "Adjustment"), ("fee", "Fee")], max_length=20)),
        ("amount", models.DecimalField(decimal_places=2, max_digits=12)),  # consider 12,2 or switch to integer minor units
        ("currency", models.CharField(default="CAD", max_length=10)),
        ("net_amount", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
        ("stripe_charge_id", models.CharField(blank=True, default="", db_index=True, max_length=255)),
        ("stripe_refund_id", models.CharField(blank=True, default="", db_index=True, max_length=255)),
        ("stripe_balance_transaction_id", models.CharField(blank=True, default="", db_index=True, max_length=255)),
        ("processed_at", models.DateTimeField(blank=True, null=True)),
        ("metadata", models.JSONField(blank=True, default=dict)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("payment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ledger_entries", to="payments.payment")),
    ],
    options={
        "ordering": ["-processed_at", "-created_at"],
        "indexes": [
            models.Index(fields=["entry_type", "processed_at"], name="payments_pa_entry_t_7ac519_idx"),
            models.Index(fields=["payment", "processed_at"], name="ledger_by_payment_processed_at"),
        ],
        "constraints": [
            models.UniqueConstraint(
                condition=models.Q(entry_type="charge") & ~models.Q(stripe_charge_id=""),
                fields=("entry_type", "stripe_charge_id"),
                name="unique_charge_entry_per_charge_id",
            ),
            models.UniqueConstraint(
                condition=models.Q(entry_type="refund") & ~models.Q(stripe_refund_id=""),
                fields=("entry_type", "stripe_refund_id"),
                name="unique_refund_entry_per_refund_id",
            ),
            models.UniqueConstraint(
                condition=~models.Q(stripe_balance_transaction_id=""),
                fields=("stripe_balance_transaction_id",),
                name="unique_ledger_per_balance_txn",
            ),
            # Optional: enforce non-negative amounts if that is your convention
            # models.CheckConstraint(name="ledger_amount_non_negative", check=models.Q(amount__gte=0)),
        ],
    },
),

# Add Payment-level constraints and uniqueness
migrations.AddConstraint(
    model_name="payment",
    constraint=models.CheckConstraint(
        name="payment_amounts_non_negative",
        check=models.Q(amount_gross__gte=0, amount_net__gte=0, amount_refunded__gte=0),
    ),
),
migrations.AddConstraint(
    model_name="payment",
    constraint=models.CheckConstraint(
        name="payment_refunded_lte_gross",
        check=models.Q(amount_refunded__lte=models.F("amount_gross")),
    ),
),
migrations.AddConstraint(
    model_name="payment",
    constraint=models.UniqueConstraint(
        condition=~models.Q(stripe_charge_id=""),
        fields=("stripe_charge_id",),
        name="unique_payment_stripe_charge_id",
    ),
),
migrations.AddConstraint(
    model_name="payment",
    constraint=models.UniqueConstraint(
        condition=~models.Q(stripe_balance_transaction_id=""),
        fields=("stripe_balance_transaction_id",),
        name="unique_payment_stripe_balance_txn_id",
    ),
),
```

### Additional notes

- Stripe/webhooks/idempotency: With the added unique constraints on charge_id, refund_id,
  and balance_transaction_id you will be protected at the DB layer against duplicate
  receipts of webhook events. Ensure your application code wraps webhook handlers in
  transaction.atomic and reacts to IntegrityError by treating it as handled
  idempotently.
- Side effects: If you expect large backfills or existing data, prefer the 3-step
  migration approach to avoid long table locks as noted above.

---

## payments/models.py

### High-level summary

- Biggest correctness gap: recalculate_totals is not automatically invoked; the
  docstring claims it is. Add signals (post_save/post_delete) to keep denormalized
  totals in sync. Wrap recalculation in transaction.atomic and use select_for_update on
  Payment to avoid races.
- Idempotency and DB portability: your conditional UniqueConstraint with condition=...
  is Postgres-only. Prefer backend-agnostic uniqueness by making stripe IDs nullable +
  unique, and add CheckConstraints to ensure the right IDs are present for the right
  entry_type.
- Data integrity: enforce that non-adjustment amounts are non-negative and that only the
  correct stripe_*_id is set per entry_type. Also validate that ledger entry currency
  matches the parent Payment currency.
- Decimal defaults: use Decimal("0") instead of 0 for DecimalField defaults to avoid
  migration churn and subtle coercion issues.
- Query efficiency: recalculate_totals can be a single aggregate with filtered Sums and
  Coalesce rather than grouping + annotate.
- Stripe invariants: consider making stripe_payment_intent_id unique to prevent multiple
  Payment rows for the same intent.

### Inline review comments and concrete fixes

1) Payment: DecimalField defaults

- Issue: Using 0 as default for DecimalFields is subtly error-prone and can generate
  unnecessary migrations in some setups.
- Suggested change:
  - Replace default=0 with default=Decimal("0") on amount_gross, amount_refunded,
    amount_net.

Suggested patch:

- from:
  amount_gross = models.DecimalField(max_digits=10, decimal_places=2, default=0)
  amount_refunded = models.DecimalField(max_digits=10, decimal_places=2, default=0)
  amount_net = models.DecimalField(max_digits=10, decimal_places=2, default=0)
- to:
  amount_gross = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
  amount_refunded = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
  amount_net = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))

1) Payment.recalculate_totals: use filtered aggregates + Coalesce; ensure atomicity at
   call site

- Comment: The current group/annotate/values_list works, but a single aggregate with
  filtered sums is simpler and reduces Python-side mapping. Also recommend documenting
  that callers should run this inside a transaction or rely on signals provided below.
- Suggested change:

Add import:

- from django.db.models.functions import Coalesce

Rewrite method body:

- from:
  totals = (
      self.ledger_entries.values("entry_type")
      .annotate(total=Sum("amount"))
      .values_list("entry_type", "total")
  )
  by_type = {entry_type: total or Decimal("0") for entry_type, total in totals}

  gross = by_type.get(PaymentLedgerEntry.EntryType.CHARGE, Decimal("0"))
  refunded = by_type.get(PaymentLedgerEntry.EntryType.REFUND, Decimal("0"))
  fee = by_type.get(PaymentLedgerEntry.EntryType.FEE, Decimal("0"))
  adjustment = by_type.get(PaymentLedgerEntry.EntryType.ADJUSTMENT, Decimal("0"))
- to:
  totals = self.ledger_entries.aggregate(
      gross=Coalesce(Sum("amount", filter=Q(entry_type=PaymentLedgerEntry.EntryType.CHARGE)), Decimal("0")),
      refunded=Coalesce(Sum("amount", filter=Q(entry_type=PaymentLedgerEntry.EntryType.REFUND)), Decimal("0")),
      fee=Coalesce(Sum("amount", filter=Q(entry_type=PaymentLedgerEntry.EntryType.FEE)), Decimal("0")),
      adjustment=Coalesce(Sum("amount", filter=Q(entry_type=PaymentLedgerEntry.EntryType.ADJUSTMENT)), Decimal("0")),
  )
  gross = totals["gross"]
  refunded = totals["refunded"]
  fee = totals["fee"]
  adjustment = totals["adjustment"]

Additionally, add docstring note:

- Note: Call this within transaction.atomic() when creating/updating ledger entries, or
  enable the provided signals to keep totals in sync safely.

1) Payment: stripe identifiers uniqueness

- Comment: For idempotency, stripe_payment_intent_id and stripe_checkout_session_id
  should generally be unique across Payment rows. At minimum, stripe_payment_intent_id
  should be unique to prevent duplicate Payment records created from retried webhooks.
- Suggested change (if business logic allows one intent per Payment):
  - Add unique=True and null=True (Stripe may not always provide it immediately).
  - If uniqueness must be scoped to enrollment_record, use
    UniqueConstraint(fields=["enrollment_record", "stripe_payment_intent_id"],
    condition=Q(stripe_payment_intent_id__isnull=False),
    name="unique_intent_per_enrollment").
- Proposed simple global uniqueness:
  - stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True,
    db_index=True, unique=True)
  - stripe_checkout_session_id = models.CharField(max_length=255, blank=True, null=True,
    db_index=True, unique=True)
  - stripe_charge_id = models.CharField(max_length=255, blank=True, null=True,
    db_index=True, unique=True)
  - stripe_balance_transaction_id can stay non-unique.

1) Payment: add __str__ for debugging

- Suggested change:
  - def __str__(self): return f"Payment #{self.pk} {self.amount} {self.currency} [{self.status}]"

1) PaymentLedgerEntry: Postgres-only conditional uniques

- Blocker: UniqueConstraint(condition=...) is only supported on PostgreSQL. If you ever
  switch or test on SQLite/MySQL, migrations fail or constraints will not be enforced.
- Fix: Make stripe_charge_id and stripe_refund_id nullable + unique at the field level,
  and add CheckConstraints that restrict which entry_type may set which ID. This yields
  backend-agnostic idempotency.

Suggested changes:

- Update fields:
  - stripe_charge_id = models.CharField(max_length=255, blank=True, null=True,
    db_index=True, unique=True)
  - stripe_refund_id = models.CharField(max_length=255, blank=True, null=True,
    db_index=True, unique=True)

- Remove the two conditional UniqueConstraints from Meta.constraints.

- Add CheckConstraints for structure and non-negative amounts:
  - models.CheckConstraint(
      name="ple_charge_requires_charge_id_positive_amount",
      check=Q(entry_type="charge", stripe_charge_id__isnull=False,
             stripe_refund_id__isnull=True, amount__gte=Decimal("0"))
           | ~Q(entry_type="charge"),
    )
  - models.CheckConstraint(
      name="ple_refund_requires_refund_id_positive_amount",
      check=Q(entry_type="refund", stripe_refund_id__isnull=False,
             stripe_charge_id__isnull=True, amount__gte=Decimal("0"))
           | ~Q(entry_type="refund"),
    )
  - models.CheckConstraint(
      name="ple_fee_no_stripe_ids_non_negative_amount",
      check=Q(entry_type="fee", stripe_charge_id__isnull=True,
             stripe_refund_id__isnull=True, amount__gte=Decimal("0"))
           | ~Q(entry_type="fee"),
    )
  - models.CheckConstraint(
      name="ple_adjustment_no_stripe_ids",
      check=Q(entry_type="adjustment", stripe_charge_id__isnull=True,
             stripe_refund_id__isnull=True)
           | ~Q(entry_type="adjustment"),
    )

- Also change Decimal defaults in PaymentLedgerEntry if any; amount stays required.

1) PaymentLedgerEntry: currency consistency and immutability

- Comment: The docstring states entries are immutable, but nothing enforces that. Also,
  ensure ledger entry currency matches parent Payment currency.
- Suggested change:
  - Add clean method:

```python
def clean(self):
    super().clean()
    if self.payment_id and self.currency != self.payment.currency:
        from django.core.exceptions import ValidationError
        raise ValidationError("Ledger entry currency must match payment currency")
```

- Optional: Enforce immutability by disallowing updates:

```python
def save(self, *args, **kwargs):
    if self.pk and kwargs.get("force_insert") is not True:
        # Disallow updates; only allow creation
        raise ValueError("PaymentLedgerEntry rows are immutable once created.")
    return super().save(*args, **kwargs)
```

Note: If you need to allow setting processed_at later, either:

- Include processed_at in creation, or
- Permit a very limited update via an allowlist of update_fields; otherwise prefer
  immutable rows for auditability.

1) Keep Payment totals in sync automatically (signals)

- Comment: The class docstrings promise automatic recalculation when ledger entries
  change, but no signals are present. Implement signals in payments/signals.py and wire
  them in AppConfig.ready() to avoid import-time side effects.
- Suggested code (new file payments/signals.py):

```python
from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Payment, PaymentLedgerEntry

@receiver([post_save, post_delete], sender=PaymentLedgerEntry)
def update_payment_totals_after_ledger_change(sender, instance, **kwargs):
    payment_id = instance.payment_id

    def _recalc():
        # Recalculate in a transaction and lock the payment row to avoid races
        from django.db import transaction as dj_tx
        with dj_tx.atomic():
            payment = Payment.objects.select_for_update().get(pk=payment_id)
            payment.recalculate_totals(save=True)

    # Run after the outer transaction commits so aggregates see all rows
    transaction.on_commit(_recalc)
```

- And in payments/apps.py:

```python
from django.apps import AppConfig

class PaymentsConfig(AppConfig):
    name = "payments"

    def ready(self):
        import payments.signals  # noqa
```

- Ensure INSTALLED_APPS uses "payments.apps.PaymentsConfig".

1) transaction.atomic usage around ledger creation

- Comment: When creating PaymentLedgerEntry rows in response to webhooks or internal
  actions, wrap:
  - creation of the ledger entry,
  - any Payment field updates (e.g., status),
  - and defer total recomputation to the signal/on_commit above.
  This keeps ledger/totals invariants correct and avoids partial updates if an
  exception is raised.

Example (service/webhook handler):

```python
with transaction.atomic():
    entry = PaymentLedgerEntry.objects.create(...)
    Payment.objects.filter(pk=entry.payment_id).update(status=Payment.Status.SUCCEEDED)
# totals recalculated on_commit by signal
```

1) Stripe/webhooks/idempotency

- Comment: Good use of WebhookEvent(stripe_event_id unique) for idempotency. Ensure your
  webhook view:
  - Verifies Stripe signature for each request via stripe.Webhook.construct_event.
  - Uses get_or_create on WebhookEvent with defaults to prevent duplicate processing on
    retries.
  - Handles out-of-order events by always deriving totals from ledger and not from event
    sequence.
- Optional improvement: store request_id and signature in WebhookEvent for audit:

```python
request_id = models.CharField(max_length=255, blank=True)
stripe_signature = models.CharField(max_length=1024, blank=True)
```

1) Minor: indexes

- You already index entry_type+processed_at and stripe_* fields. With unique=True on
  stripe IDs, the unique index covers lookup too. Consider adding an index on
  payment_id, entry_type for common aggregations:
  - models.Index(fields=["payment", "entry_type"])

1) Payment.amount validation

- Comment: For most cases, Payment.amount should be non-negative.
- Suggested change:

```python
from django.core.validators import MinValueValidator
amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
```

### Complete revised Meta for PaymentLedgerEntry (example)

```python
class Meta:
    ordering = ["-processed_at", "-created_at"]
    indexes = [
        models.Index(fields=["entry_type", "processed_at"]),
        models.Index(fields=["payment", "entry_type"]),
    ]
    constraints = [
        models.CheckConstraint(
            name="ple_charge_requires_charge_id_positive_amount",
            check=Q(entry_type="charge", stripe_charge_id__isnull=False, stripe_refund_id__isnull=True, amount__gte=Decimal("0"))
                 | ~Q(entry_type="charge"),
        ),
        models.CheckConstraint(
            name="ple_refund_requires_refund_id_positive_amount",
            check=Q(entry_type="refund", stripe_refund_id__isnull=False, stripe_charge_id__isnull=True, amount__gte=Decimal("0"))
                 | ~Q(entry_type="refund"),
        ),
        models.CheckConstraint(
            name="ple_fee_no_stripe_ids_non_negative_amount",
            check=Q(entry_type="fee", stripe_charge_id__isnull=True, stripe_refund_id__isnull=True, amount__gte=Decimal("0"))
                 | ~Q(entry_type="fee"),
        ),
        models.CheckConstraint(
            name="ple_adjustment_no_stripe_ids",
            check=Q(entry_type="adjustment", stripe_charge_id__isnull=True, stripe_refund_id__isnull=True)
                 | ~Q(entry_type="adjustment"),
        ),
    ]
```

### Accounting invariants and side effects checklist

- Denormalized totals are always recomputed after ledger changes (signals + on_commit).
- Amount signs:
  - CHARGE, REFUND, FEE: non-negative.
  - ADJUSTMENT: either sign allowed.
- Idempotency:
  - Unique stripe IDs across ledger entries (unique=True + checks).
  - Unique WebhookEvent.stripe_event_id across processed events.
- Currency consistency:
  - Enforced in model.clean; ensure full_clean() is called in service layer or admin.
    If you rely on forms/admin, it will run. For programmatic creates, call full_clean()
    before save or validate inputs in the service layer.
- Concurrency:
  - Recalc runs inside a fresh atomic block with select_for_update on Payment to
    serialize concurrent updates and avoid lost updates on totals.

### Migration impact

- Changing defaults to Decimal("0") will create a simple migration.
- Making stripe_* fields nullable + unique requires a data migration to set existing
  "" values to NULL before adding uniqueness.
  - Example data migration step: update payments_paymentledgerentry set stripe_charge_id
    = NULL where stripe_charge_id = "";
- Removing conditional unique constraints and adding CheckConstraints is safe across
  backends.

If you want me to generate the exact migration operations for the above changes, I can
draft them.

---

## payments/stripe_client.py

### PR review comments (inline)

- Imports/top of file
  - Nit: Consider adding typing for metadata coercion and random jitter if you adopt
    suggestions below. Not strictly necessary right now.

- StripeClient.create_checkout_session: currency exponent handling
  - Bug/blocker: _to_cents() assumes two-decimal currencies. Stripe expects unit_amount
    in the smallest currency unit, which varies by currency (zero-decimal: JPY, KRW,
    etc.; three-decimal: BHD, KWD, JOD, OMR, TND). This will silently overcharge/
    undercharge in those currencies.
  - Fix: Compute the correct exponent per currency and reject amounts that have too many
    fractional digits for the currency instead of rounding. Also validate positive
    non-zero amounts.

- StripeClient.create_checkout_session: transient error handling
  - Bug: stripe.error.TimeoutError does not exist in stripe-python. Referencing it inside
    except will raise AttributeError at runtime when the try block is hit, preventing
    proper error handling.
  - Fix: Remove TimeoutError. For timeouts, stripe raises APIConnectionError. Optionally
    include IdempotencyError and AuthenticationError/PermissionError handling for clearer
    semantics.

- StripeClient.create_checkout_session: idempotency and request options
  - Improvement: Pass request options (api_key, idempotency_key) as request options
    kwargs, not mixed into params. Also avoid sending idempotency_key=None.
  - Correctness: Using the same idempotency key across retries is good. Adding a bit of
    jitter to backoff is recommended per Stripe's guidance.

- StripeClient.create_checkout_session: metadata placement
  - Improvement: Checkout Session metadata is not automatically copied to the
    PaymentIntent. If you rely on metadata in payment_intent.succeeded webhooks, add
    payment_intent_data={"metadata": metadata} so webhooks can correlate without having
    to fetch the checkout session.

- StripeClient.create_checkout_session: payment method configuration
  - Suggestion: payment_method_types is static and less flexible. Stripe recommends
    automatic_payment_methods for most cases. If you want strictly "card", keep as-is,
    otherwise consider:
    automatic_payment_methods={"enabled": True}
  - Not a blocker if you need to force card-only.

- StripeClient._to_cents
  - Bug: See currency exponent note above. Also the current quantize may round silently.
    You should fail fast when the amount has invalid precision for the currency.

- Logging
  - Improvement: Include exc_info=True so your logs have stack traces. Avoid leaking
    sensitive request details; current logs look safe.

- Side effects: time.sleep in web requests
  - Note: Sleeping in a Django request thread can tie up workers. This might be
    acceptable given the low retry count, but consider delegating retries to a task
    queue if this code runs on the request path with tight SLAs.

### Concrete fixes (suggested patch)

- Handle currency exponents correctly.
- Fix exception classes.
- Pass request options cleanly.
- Copy metadata to PaymentIntent.
- Add jitter to backoff.
- Validate amount > 0 and precision.

Patch:

```diff
diff --git a/payments/stripe_client.py b/payments/stripe_client.py
index 0978f63..b8f52ac 100644
--- a/payments/stripe_client.py
+++ b/payments/stripe_client.py
@@ -1,12 +1,16 @@
 from __future__ import annotations

 import logging
 import time
+import random
 from dataclasses import dataclass
 from decimal import Decimal
+from typing import Any, Mapping


 class StripeClientError(Exception):
     """Raised when Stripe API calls fail."""


 @dataclass
@@ -31,18 +35,19 @@ class StripeClient:
         idempotency_key: str | None = None,
     ) -> StripeSession:
         stripe = self._import_stripe()
-        unit_amount = self._to_cents(amount)
+        unit_amount = self._amount_to_unit(amount=amount, currency=currency)

         params = {
-            "api_key": self.api_key,
-            "payment_method_types": ["card"],
+            # Consider automatic payment methods unless you need card-only:
+            # "automatic_payment_methods": {"enabled": True},
+            "payment_method_types": ["card"],
             "mode": "payment",
             "line_items": [
                 {
                     "quantity": 1,
                     "price_data": {
-                        "currency": currency.lower(),
+                        "currency": currency.lower(),
                         "unit_amount": unit_amount,
                         "product_data": {"name": product_name},
                     },
                 }
             ],
             "success_url": success_url,
             "cancel_url": cancel_url,
-            "metadata": metadata,
+            "metadata": self._coerce_metadata(metadata),
+            # Ensure metadata is also present on the PaymentIntent for webhook correlation
+            "payment_intent_data": {"metadata": self._coerce_metadata(metadata)},
         }

         if customer_email:
             params["customer_email"] = customer_email

+        request_options: dict[str, Any] = {"api_key": self.api_key}
+        if idempotency_key:
+            request_options["idempotency_key"] = idempotency_key
+
         for attempt in range(self.max_retries + 1):
             try:
                 session = stripe.checkout.Session.create(
-                    **params,
-                    idempotency_key=idempotency_key,
+                    **params,
+                    **request_options,
                 )
                 return StripeSession(
                     id=session.id,
                     url=session.url,
                     payment_intent=getattr(session, "payment_intent", None),
                 )
-            except stripe.error.InvalidRequestError as exc:
+            except (stripe.error.InvalidRequestError, getattr(stripe.error, "IdempotencyError", Exception)) as exc:
                 self.logger.error(
-                    "Stripe invalid request error",
-                    extra={"error": str(exc), "attempt": attempt + 1},
+                    "Stripe invalid or idempotency error",
+                    extra={"error": str(exc), "attempt": attempt + 1},
+                    exc_info=True,
                 )
                 raise StripeClientError(
                     "Payment request was invalid. Please contact support."
                 ) from exc
+            except (stripe.error.AuthenticationError, stripe.error.PermissionError) as exc:
+                self.logger.error(
+                    "Stripe authentication/permission error",
+                    extra={"error": str(exc), "attempt": attempt + 1},
+                    exc_info=True,
+                )
+                raise StripeClientError(
+                    "Payment configuration error. Please contact support."
+                ) from exc
             except (
                 stripe.error.APIConnectionError,
                 stripe.error.RateLimitError,
                 stripe.error.APIError,
-                stripe.error.TimeoutError,
             ) as exc:
                 self.logger.warning(
                     "Stripe transient error",
-                    extra={"error": str(exc), "attempt": attempt + 1},
+                    extra={"error": str(exc), "attempt": attempt + 1},
+                    exc_info=True,
                 )
                 if attempt >= self.max_retries:
                     raise StripeClientError(
                         "Stripe API is unavailable. Please try again shortly."
                     ) from exc
-                backoff_seconds = min(2**attempt, 8)
-                time.sleep(backoff_seconds)
+                backoff_seconds = min(2**attempt, 8) + random.uniform(0, 0.25)
+                time.sleep(backoff_seconds)
             except stripe.error.StripeError as exc:
                 self.logger.error(
                     "Stripe error",
-                    extra={"error": str(exc), "attempt": attempt + 1},
+                    extra={"error": str(exc), "attempt": attempt + 1},
+                    exc_info=True,
                 )
                 raise StripeClientError(
                     "Payment processing failed. Please try again."
                 ) from exc

         # This should never be reached since all code paths return or raise
         raise StripeClientError("Unexpected error: retry loop completed without result")

-    @staticmethod
-    def _to_cents(amount: Decimal) -> int:
-        return int((amount * 100).quantize(Decimal("1")))
+    @staticmethod
+    def _currency_exponent(currency: str) -> int:
+        """Return number of decimal places for the currency (Stripe smallest unit exponent)."""
+        c = currency.upper()
+        zero_decimal = {
+            "BIF", "CLP", "DJF", "GNF", "JPY", "KMF", "KRW", "MGA", "PYG",
+            "RWF", "UGX", "VND", "VUV", "XAF", "XOF", "XPF",
+        }
+        three_decimal = {"BHD", "JOD", "KWD", "OMR", "TND"}
+        if c in zero_decimal:
+            return 0
+        if c in three_decimal:
+            return 3
+        return 2
+
+    def _amount_to_unit(self, *, amount: Decimal, currency: str) -> int:
+        """Convert a Decimal major unit amount into the integer smallest unit for Stripe."""
+        if amount <= Decimal("0"):
+            raise StripeClientError("Amount must be greater than 0.")
+        exp = self._currency_exponent(currency)
+        # Ensure amount does not have more fractional digits than supported
+        quantum = Decimal(10) ** -exp  # e.g., 0.01 for exp=2
+        try:
+            normalized = amount.quantize(quantum)
+        except Exception:
+            # If quantize fails due to context traps
+            raise StripeClientError("Invalid amount precision.")
+        if normalized != amount:
+            raise StripeClientError("Amount has too many decimal places for the currency.")
+        factor = 10**exp
+        return int((amount * factor).to_integral_value())
+
+    @staticmethod
+    def _coerce_metadata(metadata: Mapping[str, Any] | None) -> dict[str, str]:
+        if not metadata:
+            return {}
+        # Stripe requires string keys/values
+        return {str(k): str(v) for k, v in metadata.items()}

     @staticmethod
     def _import_stripe():
         try:
             import stripe
         except ImportError as exc:
             raise StripeClientError(
                 "Stripe SDK is not installed. Please contact support."
             ) from exc
         return stripe
```

Notes:

- No Django ORM/transactions/authz in this module; nothing to check there.
