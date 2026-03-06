# CLAUDE.md

## COPPA/PIPEDA Compliance (Children Under 13)

**Strategy:** OAuth-only signup for ALL users. We don't collect dates of birth or determine ages. Children access via parent-managed Google Family Link or Microsoft Family Safety accounts. See `/docs/coppa-pipeda-compliance.md` for details.

---

## Project Overview

Production-ready Django 6.0/Wagtail 7.2.1 educational platform with SCORM LMS, Stripe payments, Twilio SMS/voicemail, unified portfolio, blog, and contact systems.

## Architecture

- **Dev Environment**: Docker Compose (PRIMARY) - PostgreSQL, pgAdmin, Mailpit, CSS builder
- **Deployment**: Railway with nixpacks
- **Styling**: Tailwind CSS (auto-built in Docker)
- **Apps**: home, lms (SCORM, prerequisites, payments), portfolio (unified client/educational), blog, communications (Twilio), payments (Stripe ledger), search
- **Settings**: `thinkelearn/settings/{base,dev,production}.py`
- **Background Tasks**: Planned for future (django.tasks) - currently synchronous in `payments/tasks.py`

## Authentication

**django-allauth**: Email-only login (username=email internally), Google/Microsoft OAuth with auto-account linking by email, honeypot spam protection (`website` field), mandatory email verification for direct signups.

**OAuth Trust Model**: Google/Microsoft trusted implicitly for email verification (COPPA compliance trust > email verification). Microsoft uses `mail`/`userPrincipalName` fields.

**Custom**: `SocialAccountAdapter`, `AccountAdapter` in `thinkelearn/backends/allauth.py` (28 tests)

**Env Vars**: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`

**URLs**: `/accounts/{login,signup,logout,password/reset,email,3rdparty,google/login,microsoft/login}`

## Commands

**Docker (PRIMARY)**: `./start.sh [setup|stop|reset|clean|rebuild]` - All commands use `docker-compose exec web python manage.py <cmd>`

**Setup**: `setup_lms --with-categories --with-tags`, `setup_portfolio`

**Testing**: Docker uses `python manage.py test`, local uses `uv run pytest` + quality tools (ruff, mypy, safety, bandit)

**Services**: localhost:8000 (web/admin), :8025 (Mailpit), :5050 (pgAdmin admin@thinkelearn.com/admin)

**Railway Env Vars**: DATABASE_URL, SECRET_KEY, ALLOWED_HOSTS, MAILTRAP_API_TOKEN, GOOGLE_CLIENT_ID/SECRET, MICROSOFT_CLIENT_ID/SECRET, TWILIO_*, optional AWS_*

## Design System (Tailwind)

**Colors**:
- Primary: Warm brown (#361612-#784421) - Headers/nav use `text/bg-primary-800`
- Secondary: Orange (#ff6600) - CTAs use `bg-secondary-500 hover:bg-secondary-600`, links use `text-secondary-500`
- Accent: Mint/cyan (cyan-50 to cyan-600) - Modern sections use `bg-cyan-600` or `bg-cyan-50`
- Neutral: Warm gray (#1c1917-#fafaf9) - Body text `text-neutral-700`, backgrounds `bg-neutral-50`, borders `border-neutral-200`

**Typography**: Inter (body), Poppins (headings)

## LMS (wagtail-lms + custom)

**Features**: SCORM 1.2/2004, prerequisites validation, enrollment limits, reviews (moderation required), ratings, instructor profiles, student dashboard, private client demos

**Models**: ExtendedCoursePage (categories, tags, duration, difficulty, prerequisites, enrollment limits, `visibility`: PUBLIC/UNLISTED/PRIVATE_DEMO with `clean()` guards), CourseCategory, CourseTag, CourseInstructor, CourseReview (is_approved=False default), LearnerDashboardPage, EnrollmentRecord (states: PENDING_PAYMENT→ACTIVE/PAYMENT_FAILED/CANCELLED/REFUNDED), ClientDemoInvite (UUID token, expiry, M2M to courses), ClientDemoEnrollment (tracks per-invite enrollments with `revoke_on_expiry`)

**Private Demo Access**: PRIVATE_DEMO courses → 404 for anonymous, 403 for unenrolled auth users. `client_demo_view` validates token, idempotently enrolls clients, skips enrollment for staff (wagtailadmin.access_admin). Session key `active_demo_token` + `lms.context_processors.active_demo` injects `demo_return_url` into all templates for persistent "Back to Demo" bar. `revoke_expired_demo_invites` management command cleans up revocable enrollments.

**URLs**: `/courses/`, `/courses/<slug>/`, `/dashboard/`, `/lms/course/<id>/play/`, `/lms/scorm-content/<package>/<file>`, `/demo/<uuid:token>/`

**Performance**: `select_related("user")` for reviews (line 272), `prefetch_related("categories","tags")` for listings (lines 108,283), `select_related("course")` for dashboard (line 423)

**Security**: Review moderation, SCORM iframe sandboxing, visibility guards prevent PRIVATE_DEMO↔PUBLIC transitions while enrollments/products exist

**Tests**: 209 tests in `lms/tests.py` (100% business logic coverage) - prerequisites, enrollment, ratings, completion tracking, demo invites, visibility guards, context processor

## Portfolio (Unified client/educational)

**Models**: PortfolioCategory (Font Awesome icons), PortfolioIndexPage (hero image, filtering), ProjectPage (`is_client_work` boolean, `client_name`, StreamField blocks: PackagedContentBlock, VideoContentBlock, GalleryContentBlock, InteractiveContentBlock)

**Security**: ZIP path traversal protection, secure extraction to `/media/portfolio_extracted/`

**Features**: GLightbox galleries, category filtering, technology tags, video embedding

**URLs**: `/portfolio/`, `/portfolio/<slug>/`, `/portfolio/package/<page_id>/<document_id>/`

**Tests**: 22 tests - ZIP validation, StreamField blocks, category filtering, client work differentiation

## Payments (Stripe + Ledger)

**Status**: Phases 1-5 COMPLETE (ready for production prep: security audit, perf testing, monitoring)

**Pricing**: FREE, FIXED, PAY_WHAT_YOU_CAN (CAD, 30-day refund window configurable per product)

**Models**:
- CourseProduct (lms/models.py): pricing types, refund windows
- EnrollmentRecord (lms/models.py): states PENDING_PAYMENT→ACTIVE/PAYMENT_FAILED/CANCELLED/REFUNDED, idempotency keys, methods: `create_for_user()`, `mark_paid()`, `transition_to()`
- Payment (payments/models.py): states INITIATED→SUCCEEDED/FAILED/REFUNDED, immutable `amount`, denormalized `amount_gross/refunded/net`, `recalculate_totals(save=True)`
- PaymentLedgerEntry (payments/models.py): types CHARGE/REFUND/ADJUSTMENT/FEE, unique constraints for idempotency, supports partial refunds
- WebhookEvent (payments/models.py): idempotency tracking (unique stripe_event_id)

**Webhooks** (payments/webhooks.py): `handle_checkout_session_completed()`, `handle_async_payment_failed()`, `handle_charge_succeeded()`, `handle_charge_refunded()` - Uses pre-check/lock/re-validate pattern, atomic transactions, row-level locking

**Security**: PCI DSS (Stripe handles cards), webhook signature verification, authorization checks, atomic transactions, audit trail

**Admin**: EnrollmentRecord (filters: status/product/refund eligibility), Payment (filters: status/refund state/date, inline ledger entries, RefundStateFilter)

**Management**: `cleanup_abandoned_enrollments` - cancels PENDING_PAYMENT >24hrs

**Tests**: 49 tests (100% business logic) - models, checkout, webhooks (full/partial/multiple refunds), emails, idempotency, regression for recalculate_totals() bug

## Testing Philosophy

**Test business logic only** - Not framework functionality (Django/Wagtail handle model creation, page hierarchy, routing, CRUD)

**Test**: Custom methods, prerequisites validation, enrollment limits, rating calculations, Twilio workflows, ZIP security, StreamField validation, category filtering, performance optimizations (select_related/prefetch_related)

**Coverage**: 55%+ overall, 100% on lms/models.py business logic. 209 LMS tests, 22 portfolio tests, 49 payment tests, 28 auth/adapter tests, plus home/blog/communications

**Files**: `home/tests/test_models.py`, `lms/tests.py`, `portfolio/tests.py`, `blog/tests/`, `communications/tests/`, `payments/tests/`, `thinkelearn/tests/test_{social,account}_adapter.py`, `test_integration.py`

## CI/CD

**GitHub Actions** (`.github/workflows/ci.yml`): Test (PostgreSQL), Lint (ruff/mypy), Security (safety/bandit), Build (CSS/static), Docker (PR only)

**Railway**: Auto-deploy from `main` branch, nixpacks build, migrations auto-run, whitenoise serves static files

**Config**: `nixpacks.toml`, `railway.toml`, `pyproject.toml`, `conftest.py`

## Key Files

**Docs**: `/docs/{site-plan,wagtail-models,tailwind-setup,ci-cd-plan,lms-implementation-plan}.md`

**Templates**: App-specific directories (Wagtail conventions)

**Static**: `<app>/static/`, `thinkelearn/static/`

## CRITICAL CONSTRAINTS

**PRODUCTION-READY** - All core functionality COMPLETE. Do NOT recreate existing functionality.

**Use Docker (PRIMARY)** - Always `docker-compose exec web python manage.py <cmd>`. Quick start: `./start.sh [setup]`

**Existing Features** (check before building):

- LMS: SCORM, prerequisites, enrollment, payments, reviews/ratings, dashboard, private client demos (209 tests, 100% coverage)
- Portfolio: Unified client/educational with ZIP security, videos, galleries (22 tests)
- Payments: Stripe checkout, ledger, refunds (49 tests)
- Auth: django-allauth email-only + Google/Microsoft OAuth with auto-linking (28 tests)
- Blog: Categories, tags, pagination
- Communications: Twilio SMS/voicemail

**Focus on**: Content creation and deployment, NOT additional development
