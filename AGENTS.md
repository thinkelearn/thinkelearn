# Repository Guidelines

## Project Structure & Modules
- `thinkelearn/`: Django project settings, URLs, core templates, and static pipeline configuration.
- Feature apps: `home/`, `blog/`, `portfolio/`, `communications/`, `lms/`, and `search/` hold pages, models, and view logic; each has its own `tests/`.
- Frontend assets: Tailwind sources live at `thinkelearn/static/css/src/`; built CSS outputs to `thinkelearn/static/css/thinkelearn.css` and is collected under `static/`.
- Tooling: `Makefile` and `start.sh` wrap Docker workflows; `docs/` contains setup notes for services (e.g., Railway, Mailtrap); `tests/` holds cross-app helpers.

## Build, Test, and Development Commands
- Docker dev loop: `make start` to boot containers; `make setup` seeds admin + sample pages; `make logs`/`make status` for diagnostics; `make reset` or `make clean` when you need a fresh slate (clean removes DB).
- Local servers: `uv run python manage.py runserver --settings=thinkelearn.settings.dev` for Django; `npm run build-css` to watch Tailwind; use `npm run build-css-prod` for a minified bundle.
- Linting/formatting: `uv run ruff check .` and `uv run ruff format .`.
- Type checks: `uv run mypy` (configured with Django plugin).

## Coding Style & Naming Conventions
- Python 3.13, Ruff-enforced: 88-char lines, double quotes, import sorting, and pyupgrade/bugbear rules; migrations excluded.
- Prefer type hints for service-like functions and serializers; keep Django settings split under `thinkelearn.settings.*`.
- Naming: snake_case for modules/functions, PascalCase for models/forms/blocks, lower_snake_case for template names, kebab-case for static assets.
- Tailwind: reuse existing brown/orange theme tokens; avoid adding ad-hoc inline styles when a utility exists.

## Testing Guidelines
- Framework: `uv run pytest` (uses `thinkelearn.settings.test`); markers available: `unit`, `integration`, `slow`.
- Coverage: enforced minimum 50%; HTML report emitted to `htmlcov/` via `--cov-report=html`.
- Placement/naming: tests live alongside apps (e.g., `home/tests/test_*.py`); prefer factory usage for fixtures (see `wagtail-factories`, `factory-boy`).
- For UI or template tweaks, add snapshot-like assertions for rendered context or response codes in the relevant app tests.

## Commit & Pull Request Guidelines
- Commits follow Conventional Commit semantics already in history (`feat:`, `fix:`, `chore:`). Scope suffixes encouraged (e.g., `feat(lms): add SCORM retries`).
- PRs should include: short summary, linked issue/reference, test evidence (`uv run pytest`, `uv run ruff check .`), and screenshots/GIFs for visible changes.
- Call out database migrations and data backfills explicitly. If touching deployment config (Railway/Docker), note required environment variables and rollout steps.
