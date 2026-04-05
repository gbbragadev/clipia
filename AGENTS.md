# Repository Guidelines

## Project Structure & Module Organization
`app/` contains the FastAPI backend, Celery worker, and shared business logic. Key areas: `app/api/` for API routes, `app/auth/` and `app/payments/` for domain modules, `app/services/` for media/TTS/transcription/composition flows, `app/db/` for SQLAlchemy models and engine setup, and `app/worker/` for async jobs. `tests/` holds the Python test suite. `frontend/` is a separate Next.js app with App Router code in `frontend/src/`, static assets in `frontend/public/`, and its own local guide in `frontend/AGENTS.md`. Database migrations live in `alembic/`; planning notes and product docs live in `docs/`.

## Build, Test, and Development Commands
Backend setup: `python -m venv .venv && source .venv/bin/activate && pip install -e .[dev]`.
Start dependencies: `docker compose up -d postgres redis`.
Run the API locally: `uvicorn app.main:app --reload`.
Run tests: `pytest`.
Apply migrations: `alembic upgrade head`.
Frontend setup: `cd frontend && npm install`.
Run the web app: `npm run dev`.
Create a production frontend build: `npm run build && npm run start`.

## Coding Style & Naming Conventions
Python uses 4-space indentation, type hints, and `snake_case` for functions, modules, and variables; keep Pydantic/SQLAlchemy classes in `PascalCase`. TypeScript/React in `frontend/src/` follows the existing 2-space indentation, `PascalCase` component names, and colocated helper modules in `camelCase` or descriptive kebab-free filenames. Keep route modules thin and push media or payment logic into `app/services/` or domain service files.

## Testing Guidelines
Use `pytest` for backend coverage. Add tests under `tests/` as `test_<feature>.py`; mirror the module or behavior being changed, for example `tests/test_payments.py`. Prefer focused unit tests for service logic and API tests for route behavior. Run `pytest` before opening a PR; if a change touches frontend behavior, include manual verification steps since no dedicated frontend test script is defined here.

## Commit & Pull Request Guidelines
Recent history follows Conventional Commit prefixes such as `feat:` and `fix:`. Keep messages imperative and scoped to one change, for example `feat: add email verification resend limit`. PRs should include a concise summary, linked issue or task when available, migration/env var notes if relevant, and screenshots or short recordings for UI changes.

## Security & Configuration Tips
Configuration is loaded from `.env` via `app/config.py`. Never commit real API keys, JWT secrets, SMTP credentials, or MercadoPago tokens. For local development, prefer the default Postgres (`localhost:5435`) and Redis (`localhost:6382`) services from `docker-compose.yml`.
