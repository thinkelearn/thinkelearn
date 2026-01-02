# PR #25 Deep Review Brief

## `home/tests/test_navigation_integration.py`

### Blockers

- Remove external deps and secrets: hard-coded localhost and credentials; tests require a manually running server.
  - Action: use `pytest-django` `live_server`, `django_db(transaction=True)`, create a user fixture; authenticate via Django `TestClient` and inject session cookie into Playwright context.

### High Priority

- Flaky waits and selectors.
  - Action: replace `networkidle` with `expect()` on visible/hidden states and attributes; prefer stable role-based or ID selectors.
- Brittle chevron assertion.
  - Action: assert a deterministic rotation class tied to `aria-expanded`, or drop cosmetic transform check and rely on `aria-expanded`.

### Medium Priority

- Outside-click flakiness.
  - Action: click a known-safe container (e.g., `main`) or use `page.mouse.click(1,1)`.
- Mobile viewport.
  - Action: use a dedicated mobile context/page fixture instead of changing viewport mid-test.
- Transactions/isolation.
  - Action: `pytestmark = [pytest.mark.django_db(transaction=True)]` at module level.

### Missing Tests

- Parametric tests for permission-driven visibility of menu items (e.g., user lacking permissions).
- Mobile-context test via dedicated fixture, not mid-test viewport changes.

## `lms/admin.py`

### Blockers

- Sensitive admin actions lack proper permission gating.
  - Action: hide actions via `get_actions` unless superuser or has_perm(`lms.can_manage_enrollments`); add custom permission in model `Meta`.
- Deletions can corrupt accounting.
  - Action: disable delete (`has_delete_permission -> False`) and remove `delete_selected`.
- Missing atomicity/concurrency control.
  - Action: wrap each transition in `transaction.atomic`; use `queryset.select_for_update()` and filter by allowed source statuses before processing.

### High Priority

- Incorrect message levels.
  - Action: use `django.contrib.messages` constants (`messages.SUCCESS`/`messages.WARNING`).

### Medium Priority

- Query efficiency.
  - Action: add `list_select_related`, `ordering`/`date_hierarchy`, `autocomplete_fields` to `CourseProductAdmin` and `EnrollmentRecordAdmin`.
- Read-only invariants.
  - Action: mark `status`/`amount_paid` readonly to force use of transition methods.

### Missing Tests

- Permissions: only authorized users see/execute actions.
- No-delete enforced for `EnrollmentRecord`.
- Partial success behavior: updated vs skipped counts, message levels.
- Concurrency: two admins acting simultaneously don’t double-transition (`select_for_update`).

## `lms/migrations/0003_courseproduct_enrollmentrecord_and_more.py`

### Blockers

- Financial history at risk: `CASCADE` on `EnrollmentRecord.user/product`.
  - Action: switch to `PROTECT` for both FKs.
- Re-enrollment blocked after terminal states.
  - Action: replace `unique(user, product)` with conditional unique excluding cancelled/refunded.
- Stripe IDs not nullable/unique when present.
  - Action: make `stripe_*` fields `null=True`, add partial unique constraints and partial indexes.

### High Priority

- `idempotency_key` type.
  - Action: use `UUIDField(unique=True, editable=False)`.
- Pricing invariants not enforced at DB.
  - Action: add `CheckConstraint`s for free/fixed/pwyc price rules and min/max relations.

### Medium Priority

- Indexing and currency.
  - Action: add `(product, status)` index; optionally add currency to `EnrollmentRecord`.

### Missing Tests

- DB-level constraint tests for pricing, `PROTECT` on delete, conditional unique on active enrollments.
- Uniqueness of non-null Stripe IDs; allow multiple rows when null.

## `lms/models.py`

### Blockers

- Races and idempotency in `create_for_user`.
  - Action: support idempotency_key get-or-create semantics; handle `IntegrityError` on `(user, product)` constraint; wrap in atomic.

### High Priority

- DB invariants only in `clean()`.
  - Action: mirror validations with `Meta` `CheckConstraint`s (pricing).
- Payment finalization semantics.
  - Action: add `finalize_payment(amount, currency, payment_intent_id, checkout_session_id)` to set Stripe fields, enforce currency, update `amount_paid`, then `mark_paid()` atomically.
- Stripe/id fields.
  - Action: `UUIDField` for `idempotency_key`; partial unique constraints for Stripe IDs (non-null).

### Medium Priority

- Concurrency on transitions.
  - Action: optimistic concurrency on status update (filter by `pk` + `old_status`); consider `select_for_update` where appropriate.

### Low Priority

- Formatting and `__str__` robustness.
  - Action: quantize amounts to 2 decimals in formatting; use `user.get_username()` in `__str__`.
- `ExtendedCoursePage` reverse guards.
  - Action: wrap `reverse()` calls to avoid `NoReverseMatch`; feature-flag or fallback.

### Missing Tests

- Idempotent enrollment creation and race (two concurrent requests).
- `finalize_payment` updates fields and enforces currency.
- Transition concurrent modification protection (lost update prevention).
- DB constraints: pricing rules; Stripe unique when present.
- `__str__` with custom user model.

## `thinkelearn/static/js/navigation.js`

### High Priority

- Accessibility/state sync gaps.
  - Action: keep `aria-expanded`/`aria-controls`/`aria-hidden` in sync for mobile and user menus; optionally use `inert` when hidden.

### Medium Priority

- Event lifecycle and globals.
  - Action: wrap in IIFE/module; bind outside-click (`pointerdown`, capture) only when open and remove on close; guard against double-binding.
- Keyboard behavior vs ARIA roles.
  - Action: either implement full menu pattern (Arrow/Home/End, focus management) or drop `role="menu"` and use disclosure pattern.

### Low Priority

- Chevron rotation via CSS class.
  - Action: toggle a class and animate via CSS; avoid inline styles.
- Multiple nav instances.
  - Action: use data-attributes and init per-container; avoid duplicate IDs.

### Missing Tests

- E2E checks: `aria-expanded` toggles; menu closes on outside click and Escape; rotation class toggles with state.

## `thinkelearn/templates/account/email.html`

### High Priority

- Form action detection on Enter.
  - Action: add hidden input `action_add` to ensure POST intent on Enter; render bound `add_email_form` to show field/non-field errors and repopulate values.

### Medium Priority

- Messages rendering.
  - Action: use membership checks on `message.tags`; optional `role="status"` `aria-live="polite"`.

### Low Priority

- UX/accessibility.
  - Action: confirm on Remove; `autocomplete="email"`; handle decorative primary radio (`aria-hidden`/`tabindex=-1`) or replace with non-interactive indicator; use named URL for dashboard.

### Missing Tests

- Template tests: Enter key path adds email; validation errors render; messages surface.

## `thinkelearn/templates/includes/navigation.html`

### Blockers

- Logout via GET.
  - Action: replace with POST form to `account_logout` with CSRF.

### High Priority

- Hard-coded URLs.
  - Action: use `{% url %}` names across links (home, about, portfolio, process, search, dashboard, contact, account_email).

### Medium Priority

- i18n and icons.
  - Action: wrap visible strings in `{% trans %}`; standardize Font Awesome classes/names to your version.
- Inline JS and incorrect ARIA state.
  - Action: remove inline handlers; ensure JS properly toggles `aria-expanded`; add data attributes for hooks.

### Low Priority

- Role-gated items and display name.
  - Action: gate dashboard link by permission/staff; show `user.get_full_name` or `get_username`; remove unused tag libs.

### Missing Tests

- Template test asserting logout is POST; permission-gated dashboard visibility.

## `thinkelearn/tests/test_social_adapter.py`

### Medium Priority

- Request and user portability.
  - Action: use `RequestFactory` for request; build user create kwargs dynamically to support custom user models.

### Low Priority

- Over-specified casing.
  - Action: assert case-insensitive equality for verified email.
- Parametrize verification flags.
  - Action: test both `email_verified` and `verified_email` via parametrize; avoid stateful mock reuse.

### Nice-to-Have

- Performance assertions.
  - Action: add query count assertions for key paths (existing login/no verified email: 0; matching user: 1).

### Missing Tests

- `pre_social_login` trims whitespace email and matches existing user.

## Must-Fix Before Merge

- Replace external deps/secrets in Playwright tests with `live_server` + session cookie auth; remove `networkidle` waits; stabilize chevron assertion. (`home/tests/test_navigation_integration.py`)
- Admin safety: permission-gate actions, disable delete, wrap actions in `transaction.atomic` with `select_for_update`, correct message levels, mark sensitive fields readonly. (`lms/admin.py`)
- Migration correctness: `PROTECT` on `EnrollmentRecord` FKs, conditional unique for active enrollments, nullable + unique Stripe IDs, `UUIDField` idempotency_key, DB `CheckConstraint`s for pricing. (`lms/migrations/0003...`)
- Models: idempotent and race-safe enrollment creation, `finalize_payment` API, DB constraints mirrored, optimistic concurrency on transitions. (`lms/models.py`)
- Logout must be POST; replace hard-coded URLs with named routes. (`thinkelearn/templates/includes/navigation.html`)

## Recommended Follow-Ups

- JS accessibility and listener lifecycle improvements for nav; align ARIA pattern choice with keyboard behavior. (`thinkelearn/static/js/navigation.js`)
- Email template: bound form rendering and Enter handling. (`thinkelearn/templates/account/email.html`)
- Social adapter tests: portability and parametric coverage; optional query-count guards. (`thinkelearn/tests/test_social_adapter.py`)
