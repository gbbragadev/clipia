"""Idempotent admin user seeder for Phase A creator-first mode.

Creates user admin@gui (gbbraga.dev@gmail.com) with plan="admin" and a high
credit balance. Password is random, printed to stdout and saved to
.admin-credentials.local (gitignored).

Schema confirmed against app/db/models.py::User (2026-04-22):
- id: UUID (generated)
- email: str (unique)
- name: str (required)
- password_hash: str (required)
- credits: int (default 2)
- plan: str (default "free"; "admin" grants admin access via
  dependencies.get_current_admin_user)
- email_verified: bool (default False)
"""

import asyncio
import secrets
import sys
from pathlib import Path

from sqlalchemy import select

from app.auth.service import hash_password
from app.db.engine import async_session
from app.db.models import User

ADMIN_EMAIL = "gbbraga.dev@gmail.com"
ADMIN_NAME = "admin@gui"
ADMIN_CREDITS = 999_999
CREDENTIALS_PATH = Path(__file__).resolve().parent.parent / ".admin-credentials.local"


async def seed_admin() -> None:
    password = secrets.token_urlsafe(24)
    pwd_hash = hash_password(password)

    async with async_session() as session:
        result = await session.execute(select(User).where(User.email == ADMIN_EMAIL))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Admin {ADMIN_EMAIL} already exists (id={existing.id}); skipping.")
            return

        user = User(
            email=ADMIN_EMAIL,
            name=ADMIN_NAME,
            password_hash=pwd_hash,
            plan="admin",
            credits=ADMIN_CREDITS,
            email_verified=True,
        )
        session.add(user)
        await session.commit()

    CREDENTIALS_PATH.write_text(
        f"email: {ADMIN_EMAIL}\npassword: {password}\n",
        encoding="utf-8",
    )
    print(f"Created admin {ADMIN_EMAIL}")
    print(f"Password written to: {CREDENTIALS_PATH}")


if __name__ == "__main__":
    asyncio.run(seed_admin())
    sys.exit(0)
