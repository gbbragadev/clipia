# Auto Shorts Generator (Clipia)

## Project Overview
Clipia is an automated short video generator (Shorts/Reels/TikTok) powered by AI. 
The system consists of a Python backend that handles heavy media processing, script generation, and API routing, alongside a React/Next.js frontend that utilizes Remotion for video rendering and preview. 

**Key Technologies:**
- **Backend**: FastAPI, Celery, SQLAlchemy (asyncpg), Alembic, Redis.
- **Media AI processing**: XTTS v2 (TTS pt-BR), faster-whisper (subtitles), FFmpeg + MoviePy (composition), Claude API (scriptwriting), SDXL (images). Requires RTX 3090 for rendering/inference.
- **Frontend**: Next.js 16 (App Router), React 19, Remotion, Tailwind CSS.

## Project Structure
- `app/`: Contains the FastAPI backend, Celery worker, and business logic.
  - `api/`: API routes.
  - `auth/`, `payments/`: Domain-specific modules.
  - `services/`: Media, TTS, transcription, and composition flows.
  - `db/`: SQLAlchemy models and engine setup.
  - `worker/`: Async Celery jobs.
- `tests/`: Python test suite (`pytest`).
- `alembic/`: Database migrations.
- `frontend/`: Next.js web application and Remotion components.
- `docs/`: Planning notes, product docs, and session logs.

## Building and Running

### Backend
1. **Environment Setup**: 
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .[dev]
   ```
2. **Start Infrastructure**: 
   ```bash
   docker compose up -d postgres redis
   ```
3. **Run the API locally**: 
   ```bash
   uvicorn app.main:app --reload
   ```
4. **Run Tests**: 
   ```bash
   pytest
   ```
5. **Apply Database Migrations**: 
   ```bash
   alembic upgrade head
   ```

### Frontend
1. **Setup dependencies**: 
   ```bash
   cd frontend && npm install
   ```
2. **Run Development Server**: 
   ```bash
   npm run dev
   ```
3. **Production Build**: 
   ```bash
   npm run build && npm run start
   ```

## Development Conventions

### Coding Style
- **Python**: Use 4-space indentation, explicit type hints, and `snake_case` for functions, modules, and variables. Use `PascalCase` for Pydantic and SQLAlchemy classes. Keep route modules thin and push domain logic into `app/services/`.
- **TypeScript/React (Frontend)**: Follow 2-space indentation, `PascalCase` component names, and colocate helper modules in `camelCase` or descriptive kebab-case filenames. Use Tailwind CSS for styling.

### Testing Guidelines
- Use `pytest` for backend coverage. Add tests under the `tests/` directory named `test_<feature>.py`.
- Prefer focused unit tests for service logic and integration tests for route behaviors.
- Always run `pytest` before opening a Pull Request.

### Commit & PR Guidelines
- Use Conventional Commit prefixes (e.g., `feat:`, `fix:`). 
- Keep commit messages imperative and scoped to a single change (e.g., `feat: add email verification resend limit`).
- Pull Requests should include a concise summary, linked issues, and UI screenshots/recordings if relevant.

### Security & Configuration
- Configuration is loaded from `.env` via `app/config.py`.
- **Never commit** real API keys, JWT secrets, SMTP credentials, or MercadoPago tokens.
- For local development, use the default Postgres (`localhost:5435`) and Redis (`localhost:6382`) settings provided by `docker-compose.yml`.
