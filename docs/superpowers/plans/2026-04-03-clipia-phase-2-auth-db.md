# ClipIA Phase 2: Autenticação & Banco de Dados

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar PostgreSQL, autenticação JWT, tabelas de usuário/jobs/waitlist, e páginas de login/registro no frontend — transformando o ClipIA de demo público em produto com contas de usuário.

**Architecture:** PostgreSQL via Docker Compose para persistência. SQLAlchemy 2.0 async como ORM com Alembic para migrações. JWT (python-jose + bcrypt) para autenticação stateless. Frontend com AuthContext React para gerenciamento de sessão e páginas de login/registro. O endpoint `/generate` passa a exigir autenticação, e jobs são associados ao usuário.

**Tech Stack:** PostgreSQL 16, SQLAlchemy 2.0 (async), Alembic, python-jose, passlib[bcrypt], Next.js App Router, React Context

---

## Decisões Técnicas

| Decisão | Escolha | Justificativa |
|---------|---------|---------------|
| ORM | SQLAlchemy 2.0 async | Idiomático com FastAPI, tipado, migrations via Alembic |
| Auth | JWT stateless | Simples, sem estado no servidor, escala horizontalmente |
| Password hash | bcrypt (passlib) | Padrão de indústria, resistente a brute force |
| DB | PostgreSQL 16 (Docker) | Já usado no servidor para outros projetos |
| Frontend state | React Context + localStorage | Leve, sem dependência extra (não precisa de Redux) |

---

## File Structure

### Backend — Novos Arquivos

| Ação | Arquivo | Responsabilidade |
|------|---------|------------------|
| Create | `app/db/__init__.py` | Package init |
| Create | `app/db/engine.py` | AsyncEngine + sessionmaker |
| Create | `app/db/models.py` | SQLAlchemy models (User, Job, Waitlist) |
| Create | `app/db/base.py` | DeclarativeBase compartilhado |
| Create | `app/auth/__init__.py` | Package init |
| Create | `app/auth/schemas.py` | Pydantic schemas (RegisterRequest, LoginRequest, TokenResponse, UserResponse) |
| Create | `app/auth/service.py` | hash_password, verify_password, create_token, decode_token |
| Create | `app/auth/routes.py` | POST /auth/register, POST /auth/login, GET /auth/me |
| Create | `app/auth/dependencies.py` | get_current_user FastAPI dependency |
| Create | `alembic.ini` | Alembic config |
| Create | `alembic/env.py` | Alembic migration environment |
| Create | `alembic/versions/001_initial.py` | First migration: users, jobs, waitlist |
| Modify | `app/main.py` | Registrar auth router, startup/shutdown DB |
| Modify | `app/config.py` | Adicionar DATABASE_URL, JWT_SECRET |
| Modify | `app/api/routes.py` | Proteger /generate com auth, salvar job no DB |
| Modify | `app/worker/tasks.py` | Atualizar status no DB (além do Redis) |
| Create | `docker-compose.yml` | PostgreSQL + Redis containers |
| Modify | `pyproject.toml` | Novas dependências |
| Create | `tests/test_auth.py` | Testes de auth |

### Frontend — Novos Arquivos

| Ação | Arquivo | Responsabilidade |
|------|---------|------------------|
| Create | `frontend/src/lib/auth.ts` | Funções de auth: login, register, getMe, logout, getToken |
| Create | `frontend/src/contexts/AuthContext.tsx` | React Context: user state, login/logout, token management |
| Create | `frontend/src/app/auth/login/page.tsx` | Página de login |
| Create | `frontend/src/app/auth/register/page.tsx` | Página de registro |
| Modify | `frontend/src/app/layout.tsx` | Envolver com AuthProvider |
| Modify | `frontend/src/components/Navbar.tsx` | Mostrar user/login no nav |
| Modify | `frontend/src/components/WaitlistForm.tsx` | Enviar para API em vez de localStorage |
| Modify | `frontend/src/hooks/useVideoGeneration.ts` | Incluir token JWT nas requests |
| Modify | `frontend/src/lib/api.ts` | Adicionar header Authorization |

---

### Task 1: Docker Compose + Dependências

**Files:**
- Create: `docker-compose.yml`
- Modify: `pyproject.toml`
- Modify: `app/config.py`
- Create: `.env.example` (atualizar)

- [ ] **Step 1: Criar docker-compose.yml**

Criar `/home/gui/projects/auto-shorts/docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: clipia
      POSTGRES_PASSWORD: clipia_dev
      POSTGRES_DB: clipia
    ports:
      - "5434:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U clipia"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6381:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  pgdata:
```

Nota: Usa portas 5434 e 6381 para não conflitar com PostgreSQL (5432/5433) e Redis (6379/6380) já em uso no servidor para outros projetos.

- [ ] **Step 2: Adicionar dependências ao pyproject.toml**

Em `pyproject.toml`, adicionar ao array `dependencies`:

```toml
dependencies = [
    # ... existentes ...
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
]
```

- [ ] **Step 3: Instalar dependências**

```bash
cd /home/gui/projects/auto-shorts
pip install -e ".[dev]"
```

- [ ] **Step 4: Atualizar config.py com DATABASE_URL e JWT_SECRET**

Em `app/config.py`, adicionar campos ao Settings:

```python
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # API Keys
    ANTHROPIC_API_KEY: str = ""
    PEXELS_API_KEY: str = ""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://clipia:clipia_dev@localhost:5434/clipia"

    # Auth
    JWT_SECRET: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Redis
    REDIS_URL: str = "redis://localhost:6381/0"

    # File Paths
    STORAGE_DIR: Path = Path("./storage")
    REFERENCE_VOICE: Path = Path("./reference_voices/narrator_ptbr.wav")
    FONT_PATH: Path = Path("./fonts/Montserrat-Bold.ttf")

    # Video specs
    VIDEO_WIDTH: int = 1080
    VIDEO_HEIGHT: int = 1920
    VIDEO_FPS: int = 30

    # GPU
    DEVICE: str = "cuda"
    WHISPER_MODEL_SIZE: str = "large-v3"
    WHISPER_COMPUTE_TYPE: str = "float16"

    # AI
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
```

- [ ] **Step 5: Atualizar .env com novas variáveis**

Adicionar ao `.env`:

```
DATABASE_URL=postgresql+asyncpg://clipia:clipia_dev@localhost:5434/clipia
JWT_SECRET=dev-secret-change-in-production-use-openssl-rand
REDIS_URL=redis://localhost:6381/0
```

- [ ] **Step 6: Subir containers e verificar**

```bash
cd /home/gui/projects/auto-shorts
docker compose up -d
docker compose ps
```

Expected: postgres e redis "healthy".

```bash
docker compose exec postgres psql -U clipia -c "SELECT 1"
```

Expected: retorna `1`.

- [ ] **Step 7: Commit**

```bash
git add docker-compose.yml pyproject.toml app/config.py .env.example
git commit -m "feat: add PostgreSQL + Redis Docker Compose and update config"
```

---

### Task 2: SQLAlchemy Models + Alembic Migrations

**Files:**
- Create: `app/db/__init__.py`
- Create: `app/db/base.py`
- Create: `app/db/engine.py`
- Create: `app/db/models.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.mako`
- Create: `alembic/versions/` (directory)

- [ ] **Step 1: Criar app/db/base.py**

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 2: Criar app/db/engine.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
```

- [ ] **Step 3: Criar app/db/__init__.py**

```python
from app.db.engine import engine, async_session, get_db
from app.db.base import Base
from app.db.models import User, Job, WaitlistEntry
```

- [ ] **Step 4: Criar app/db/models.py**

```python
import uuid
from datetime import datetime

from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, default=2)  # 2 free credits on register
    plan: Mapped[str] = mapped_column(String(50), default="free")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    jobs: Mapped[list["Job"]] = relationship(back_populates="user")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    style: Mapped[str] = mapped_column(String(50), nullable=False)
    duration_target: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    current_step: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    script: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="jobs")


class WaitlistEntry(Base):
    __tablename__ = "waitlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 5: Configurar Alembic**

Criar `alembic.ini`:

```ini
[alembic]
script_location = alembic
prepend_sys_path = .

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

Criar `alembic/env.py`:

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.db.base import Base
from app.db.models import User, Job, WaitlistEntry  # noqa: F401 - import to register models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=settings.DATABASE_URL, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(settings.DATABASE_URL)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

Criar `alembic/script.mako`:

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

Criar diretório: `mkdir -p alembic/versions`

- [ ] **Step 6: Gerar e rodar primeira migração**

```bash
cd /home/gui/projects/auto-shorts
alembic revision --autogenerate -m "initial: users, jobs, waitlist"
alembic upgrade head
```

Verificar:

```bash
docker compose exec postgres psql -U clipia -c "\dt"
```

Expected: tabelas `users`, `jobs`, `waitlist`, `alembic_version`.

- [ ] **Step 7: Commit**

```bash
git add app/db/ alembic.ini alembic/
git commit -m "feat: add SQLAlchemy models and Alembic migrations for users, jobs, waitlist"
```

---

### Task 3: Auth Service (hash, JWT, verify)

**Files:**
- Create: `app/auth/__init__.py`
- Create: `app/auth/service.py`
- Create: `app/auth/schemas.py`
- Create: `tests/test_auth_service.py`

- [ ] **Step 1: Criar app/auth/__init__.py**

```python
```

(Arquivo vazio.)

- [ ] **Step 2: Criar app/auth/schemas.py**

```python
from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    credits: int
    plan: str
```

- [ ] **Step 3: Criar app/auth/service.py**

```python
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Returns user_id or None if invalid/expired."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
```

- [ ] **Step 4: Escrever teste**

Criar `tests/test_auth_service.py`:

```python
from app.auth.service import hash_password, verify_password, create_access_token, decode_access_token


def test_password_hash_and_verify():
    hashed = hash_password("mysecretpassword")
    assert hashed != "mysecretpassword"
    assert verify_password("mysecretpassword", hashed)
    assert not verify_password("wrongpassword", hashed)


def test_jwt_create_and_decode():
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    token = create_access_token(user_id)
    decoded = decode_access_token(token)
    assert decoded == user_id


def test_jwt_invalid_token():
    assert decode_access_token("invalid.token.here") is None
```

- [ ] **Step 5: Rodar testes**

```bash
cd /home/gui/projects/auto-shorts
pytest tests/test_auth_service.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add app/auth/ tests/test_auth_service.py
git commit -m "feat: add auth service — password hashing and JWT tokens"
```

---

### Task 4: Auth Routes (register, login, me)

**Files:**
- Create: `app/auth/dependencies.py`
- Create: `app/auth/routes.py`
- Modify: `app/main.py`
- Create: `tests/test_auth_routes.py`

- [ ] **Step 1: Criar app/auth/dependencies.py**

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import decode_access_token
from app.db.engine import get_db
from app.db.models import User

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado")

    return user
```

- [ ] **Step 2: Criar app/auth/routes.py**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.auth.service import create_access_token, hash_password, verify_password
from app.db.engine import get_db
from app.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email já cadastrado")

    user = User(
        email=body.email,
        name=body.name,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou senha incorretos")

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        credits=user.credits,
        plan=user.plan,
    )
```

- [ ] **Step 3: Registrar auth router no main.py**

Modificar `app/main.py`:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.auth.routes import router as auth_router
from app.db.engine import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="ClipIA API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restringir para dominio do frontend em producao
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Escrever testes de auth routes**

Criar `tests/test_auth_routes.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_register_and_login(client):
    # Register
    res = await client.post("/api/v1/auth/register", json={
        "email": "test@clipia.com",
        "name": "Test User",
        "password": "securepass123",
    })
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data

    # Login with same credentials
    res = await client.post("/api/v1/auth/login", json={
        "email": "test@clipia.com",
        "password": "securepass123",
    })
    assert res.status_code == 200
    token = res.json()["access_token"]

    # Get me
    res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    user = res.json()
    assert user["email"] == "test@clipia.com"
    assert user["credits"] == 2


@pytest.mark.asyncio
async def test_duplicate_email(client):
    await client.post("/api/v1/auth/register", json={
        "email": "dupe@clipia.com",
        "name": "Dupe",
        "password": "pass123",
    })
    res = await client.post("/api/v1/auth/register", json={
        "email": "dupe@clipia.com",
        "name": "Dupe2",
        "password": "pass456",
    })
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_wrong_password(client):
    await client.post("/api/v1/auth/register", json={
        "email": "wrong@clipia.com",
        "name": "Wrong",
        "password": "correctpass",
    })
    res = await client.post("/api/v1/auth/login", json={
        "email": "wrong@clipia.com",
        "password": "wrongpass",
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token(client):
    res = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalidtoken"})
    assert res.status_code == 401
```

- [ ] **Step 5: Rodar testes**

```bash
pytest tests/test_auth_routes.py -v
```

Expected: 4 passed (requer DB rodando).

- [ ] **Step 6: Commit**

```bash
git add app/auth/ app/main.py tests/test_auth_routes.py
git commit -m "feat: add auth routes — register, login, me with JWT"
```

---

### Task 5: Proteger /generate com Auth + Salvar Job no DB

**Files:**
- Modify: `app/api/routes.py`
- Modify: `app/worker/tasks.py`

- [ ] **Step 1: Atualizar routes.py para exigir auth e salvar no DB**

Substituir o conteúdo de `app/api/routes.py`:

```python
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.config import settings
from app.db.engine import get_db
from app.db.models import Job, User
from app.models import GenerateRequest, JobStatus
from app.worker.tasks import dispatch_pipeline

router = APIRouter()


@router.post("/generate", response_model=JobStatus)
async def generate_video(
    body: GenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.credits < 1:
        raise HTTPException(status_code=402, detail="Créditos insuficientes")

    job = Job(
        user_id=user.id,
        topic=body.topic,
        style=body.style,
        duration_target=body.duration_target,
        status="queued",
    )
    db.add(job)

    user.credits -= 1
    await db.commit()
    await db.refresh(job)

    job_id = str(job.id)

    # Keep Redis for real-time polling (fast reads)
    import redis
    _redis = redis.from_url(settings.REDIS_URL)
    _redis.hset(f"job:{job_id}", mapping={
        "status": "queued",
        "progress": "0",
        "current_step": "",
        "error": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    dispatch_pipeline(job_id, body.topic, body.style, body.duration_target)

    return JobStatus(
        job_id=job_id,
        status="queued",
        progress=0,
        current_step=None,
        error=None,
        created_at=datetime.now(timezone.utc).isoformat(),
        download_url=None,
    )


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    import redis
    _redis = redis.from_url(settings.REDIS_URL)
    data = _redis.hgetall(f"job:{job_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    status_val = data.get(b"status", b"unknown").decode()
    download_url = None
    if status_val == "completed":
        download_url = f"/api/v1/jobs/{job_id}/download"

    return JobStatus(
        job_id=job_id,
        status=status_val,
        progress=float(data.get(b"progress", b"0")),
        current_step=data.get(b"current_step", b"").decode() or None,
        error=data.get(b"error", b"").decode() or None,
        created_at=data.get(b"created_at", b"").decode(),
        download_url=download_url,
    )


@router.get("/jobs/{job_id}/download")
async def download_video(job_id: str):
    video_path = settings.STORAGE_DIR / "output" / f"{job_id}.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")
    return FileResponse(str(video_path), media_type="video/mp4", filename=f"clipia-{job_id[:8]}.mp4")
```

- [ ] **Step 2: Atualizar task_finalize para atualizar DB**

Em `app/worker/tasks.py`, modificar a função `task_finalize` para também atualizar o status do job no PostgreSQL. Adicionar ao final da task_finalize:

```python
# After the existing Redis update, add DB update:
from app.db.engine import async_session
from app.db.models import Job
from sqlalchemy import select
import asyncio

async def _update_job_db(job_id: str, video_url: str):
    async with async_session() as session:
        result = await session.execute(select(Job).where(Job.id == uuid.UUID(job_id)))
        job = result.scalar_one_or_none()
        if job:
            job.status = "completed"
            job.progress = 1.0
            job.video_url = video_url
            job.completed_at = datetime.now(timezone.utc)
            await session.commit()

asyncio.run(_update_job_db(job_id, f"/api/v1/jobs/{job_id}/download"))
```

- [ ] **Step 3: Commit**

```bash
git add app/api/routes.py app/worker/tasks.py
git commit -m "feat: protect /generate with auth, deduct credits, save job to DB"
```

---

### Task 6: Waitlist Backend Endpoint

**Files:**
- Modify: `app/api/routes.py` (adicionar endpoint)

- [ ] **Step 1: Adicionar POST /waitlist ao routes.py**

Adicionar ao final de `app/api/routes.py`:

```python
from pydantic import BaseModel
from app.db.models import WaitlistEntry


class WaitlistRequest(BaseModel):
    email: str


@router.post("/waitlist", status_code=201)
async def join_waitlist(body: WaitlistRequest, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    result = await db.execute(select(WaitlistEntry).where(WaitlistEntry.email == body.email))
    if result.scalar_one_or_none() is not None:
        return {"message": "Email já cadastrado na waitlist"}

    entry = WaitlistEntry(email=body.email)
    db.add(entry)
    await db.commit()
    return {"message": "Adicionado à waitlist com sucesso"}
```

Note: Este endpoint NÃO requer autenticação — é público.

- [ ] **Step 2: Commit**

```bash
git add app/api/routes.py
git commit -m "feat: add public /waitlist endpoint"
```

---

### Task 7: Frontend — Auth Library + Context

**Files:**
- Create: `frontend/src/lib/auth.ts`
- Create: `frontend/src/contexts/AuthContext.tsx`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Criar frontend/src/lib/auth.ts**

```typescript
const API_BASE = "";

export interface User {
  id: string;
  email: string;
  name: string;
  credits: number;
  plan: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("clipia_token");
}

export function setToken(token: string): void {
  localStorage.setItem("clipia_token", token);
}

export function clearToken(): void {
  localStorage.removeItem("clipia_token");
}

export async function register(email: string, name: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, name, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Erro ao registrar" }));
    throw new Error(err.detail || "Erro ao registrar");
  }
  return res.json();
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Email ou senha incorretos" }));
    throw new Error(err.detail || "Email ou senha incorretos");
  }
  return res.json();
}

export async function getMe(): Promise<User> {
  const token = getToken();
  if (!token) throw new Error("Não autenticado");
  const res = await fetch(`${API_BASE}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    clearToken();
    throw new Error("Sessão expirada");
  }
  return res.json();
}
```

- [ ] **Step 2: Criar frontend/src/contexts/AuthContext.tsx**

```tsx
"use client";

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import {
  type User,
  getMe,
  login as authLogin,
  register as authRegister,
  setToken,
  clearToken,
  getToken,
} from "@/lib/auth";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, name: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setLoading(false);
      return;
    }
    getMe()
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await authLogin(email, password);
    setToken(res.access_token);
    const me = await getMe();
    setUser(me);
  }, []);

  const register = useCallback(async (email: string, name: string, password: string) => {
    const res = await authRegister(email, name, password);
    setToken(res.access_token);
    const me = await getMe();
    setUser(me);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  return (
    <AuthContext value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
```

- [ ] **Step 3: Atualizar api.ts para incluir token nas requests**

Substituir `frontend/src/lib/api.ts`:

```typescript
import { getToken } from "./auth";

const API_BASE = "";

function authHeaders(): Record<string, string> {
  const token = getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

export interface GenerateRequest {
  topic: string;
  style: string;
  duration_target: number;
}

export interface JobStatus {
  job_id: string;
  status: "queued" | "processing" | "completed" | "failed";
  progress: number;
  current_step: string | null;
  error: string | null;
  created_at: string;
  download_url: string | null;
}

export async function generateVideo(req: GenerateRequest): Promise<{ job_id: string }> {
  const res = await fetch(`${API_BASE}/api/v1/generate`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Erro ao gerar vídeo" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${API_BASE}/api/v1/jobs/${jobId}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export function getDownloadUrl(jobId: string): string {
  return `${API_BASE}/api/v1/jobs/${jobId}/download`;
}
```

- [ ] **Step 4: Envolver layout.tsx com AuthProvider**

Modificar `frontend/src/app/layout.tsx` — envolver `{children}` com AuthProvider:

```tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import FilmGrain from "@/components/FilmGrain";
import { AuthProvider } from "@/contexts/AuthContext";

// ... (metadata stays the same) ...

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR" className={`${inter.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <FilmGrain />
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/auth.ts frontend/src/contexts/AuthContext.tsx frontend/src/lib/api.ts frontend/src/app/layout.tsx
git commit -m "feat: add auth context, token management, and protected API calls"
```

---

### Task 8: Frontend — Páginas de Login e Registro

**Files:**
- Create: `frontend/src/app/auth/login/page.tsx`
- Create: `frontend/src/app/auth/register/page.tsx`

- [ ] **Step 1: Criar página de login**

Criar `frontend/src/app/auth/login/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao entrar");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="card w-full max-w-md p-8">
        <h1 className="text-2xl font-bold text-center mb-2">
          Entrar no <span className="bg-gradient-to-r from-purple-500 to-blue-500 bg-clip-text text-transparent">ClipIA</span>
        </h1>
        <p className="text-slate-400 text-center text-sm mb-8">
          Crie vídeos curtos com IA
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-red-400 text-sm">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="email" className="block text-sm text-slate-300 mb-1">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/50"
              placeholder="seu@email.com"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm text-slate-300 mb-1">Senha</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/50"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full py-2.5 rounded-lg font-semibold disabled:opacity-50"
          >
            {loading ? "Entrando..." : "Entrar"}
          </button>
        </form>

        <p className="text-center text-sm text-slate-400 mt-6">
          Não tem conta?{" "}
          <Link href="/auth/register" className="text-purple-400 hover:text-purple-300">
            Criar conta
          </Link>
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Criar página de registro**

Criar `frontend/src/app/auth/register/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";

export default function RegisterPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password.length < 6) {
      setError("Senha deve ter pelo menos 6 caracteres");
      return;
    }
    setLoading(true);
    try {
      await register(email, name, password);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar conta");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="card w-full max-w-md p-8">
        <h1 className="text-2xl font-bold text-center mb-2">
          Criar conta no <span className="bg-gradient-to-r from-purple-500 to-blue-500 bg-clip-text text-transparent">ClipIA</span>
        </h1>
        <p className="text-slate-400 text-center text-sm mb-8">
          Ganhe 2 créditos grátis para começar
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-red-400 text-sm">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="name" className="block text-sm text-slate-300 mb-1">Nome</label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/50"
              placeholder="Seu nome"
            />
          </div>

          <div>
            <label htmlFor="email" className="block text-sm text-slate-300 mb-1">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/50"
              placeholder="seu@email.com"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm text-slate-300 mb-1">Senha</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/50"
              placeholder="Mínimo 6 caracteres"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full py-2.5 rounded-lg font-semibold disabled:opacity-50"
          >
            {loading ? "Criando conta..." : "Criar conta grátis"}
          </button>
        </form>

        <p className="text-center text-sm text-slate-400 mt-6">
          Já tem conta?{" "}
          <Link href="/auth/login" className="text-purple-400 hover:text-purple-300">
            Entrar
          </Link>
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verificar build**

```bash
cd /home/gui/projects/auto-shorts/frontend
npx next build 2>&1 | tail -10
```

Expected: Build sem erros, novas rotas `/auth/login` e `/auth/register` listadas.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/auth/
git commit -m "feat: add login and register pages"
```

---

### Task 9: Atualizar Navbar + WaitlistForm

**Files:**
- Modify: `frontend/src/components/Navbar.tsx`
- Modify: `frontend/src/components/WaitlistForm.tsx`

- [ ] **Step 1: Atualizar Navbar para mostrar user/login**

Em `frontend/src/components/Navbar.tsx`, adicionar import do useAuth e condicional no header:

Após os links existentes (Demo, Como funciona, Acesso antecipado), adicionar no canto direito:

```tsx
import { useAuth } from "@/contexts/AuthContext";

// Inside the component:
const { user, logout } = useAuth();

// In the JSX, replace the existing CTA button with:
{user ? (
  <div className="flex items-center gap-3">
    <span className="text-sm text-slate-300">
      <span className="text-purple-400 font-semibold">{user.credits}</span> créditos
    </span>
    <button onClick={logout} className="text-sm text-slate-400 hover:text-white">
      Sair
    </button>
  </div>
) : (
  <a href="/auth/login" className="btn-primary text-sm px-4 py-1.5 rounded-full">
    Entrar
  </a>
)}
```

- [ ] **Step 2: Atualizar WaitlistForm para enviar ao backend**

Modificar `frontend/src/components/WaitlistForm.tsx` para fazer POST na API ao invés de salvar no localStorage:

```tsx
// Replace the submit handler:
async function handleSubmit(e: React.FormEvent) {
  e.preventDefault();
  setLoading(true);
  try {
    const res = await fetch("/api/v1/waitlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    if (res.ok) {
      setSubmitted(true);
      localStorage.setItem("waitlist_email", email);
    }
  } catch {
    // Fallback: save locally if API is down
    setSubmitted(true);
    localStorage.setItem("waitlist_email", email);
  } finally {
    setLoading(false);
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Navbar.tsx frontend/src/components/WaitlistForm.tsx
git commit -m "feat: update navbar with auth state and waitlist with API backend"
```

---

### Task 10: Verificação Final da Fase 2

- [ ] **Step 1: Verificar containers rodando**

```bash
docker compose ps
```

Expected: postgres e redis "healthy".

- [ ] **Step 2: Verificar migração aplicada**

```bash
docker compose exec postgres psql -U clipia -c "\dt"
```

Expected: tabelas users, jobs, waitlist, alembic_version.

- [ ] **Step 3: Testar fluxo de auth**

```bash
# Register
curl -s -X POST http://localhost:8005/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@clipia.com","name":"Test","password":"test123"}' | python3 -m json.tool

# Login
curl -s -X POST http://localhost:8005/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@clipia.com","password":"test123"}' | python3 -m json.tool

# Me (com token do login)
TOKEN="<token from above>"
curl -s http://localhost:8005/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

- [ ] **Step 4: Testar waitlist**

```bash
curl -s -X POST http://localhost:8005/api/v1/waitlist \
  -H "Content-Type: application/json" \
  -d '{"email":"waitlist@clipia.com"}' | python3 -m json.tool
```

Expected: `{"message": "Adicionado à waitlist com sucesso"}`

- [ ] **Step 5: Frontend build limpo**

```bash
cd /home/gui/projects/auto-shorts/frontend
npx next build 2>&1 | tail -15
```

Expected: Build sem erros, rotas `/auth/login`, `/auth/register` presentes.

- [ ] **Step 6: Rodar todos os testes**

```bash
cd /home/gui/projects/auto-shorts
pytest tests/ -v
```

Expected: Todos passam.
