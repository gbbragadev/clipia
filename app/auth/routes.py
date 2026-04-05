import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.email import generate_otp, otp_expiry, send_verification_email
from app.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    ResendCodeRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)
from app.auth.service import create_access_token, hash_password, verify_password
from app.config import settings
from app.db.engine import get_db
from app.db.models import User
from app.utils.locks import get_lock

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def register(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    async with get_lock(f"register:{body.email}"):
        result = await db.execute(select(User).where(User.email == body.email))
        if result.scalar_one_or_none() is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email ja cadastrado")

        code = generate_otp()
        user = User(
            email=body.email,
            name=body.name,
            password_hash=hash_password(body.password),
            credits=0,
            email_verified=False,
            verification_code=code,
            verification_expires=otp_expiry(),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        asyncio.get_event_loop().run_in_executor(
            None, send_verification_email, body.email, code, body.name
        )

        token = create_access_token(str(user.id))
        return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou senha incorretos")

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.post("/verify-email")
@limiter.limit("5/minute")
async def verify_email(request: Request, body: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    async with get_lock(f"verify-email:{body.email}"):
        result = await db.execute(select(User).where(User.email == body.email))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="Usuario nao encontrado")

        if user.email_verified:
            return {"status": "already_verified"}

        if not user.verification_code or not user.verification_expires:
            raise HTTPException(status_code=400, detail="Nenhum codigo pendente")

        if datetime.now(timezone.utc) > _ensure_utc(user.verification_expires):
            raise HTTPException(status_code=400, detail="Codigo expirado. Solicite um novo.")

        if user.verification_code != body.code:
            raise HTTPException(status_code=400, detail="Codigo incorreto")

        user.email_verified = True
        user.verification_code = None
        user.verification_expires = None
        user.credits = 2
        await db.commit()

        return {"status": "verified", "credits": 2}


@router.post("/resend-code")
@limiter.limit("3/minute")
async def resend_code(request: Request, body: ResendCodeRequest, db: AsyncSession = Depends(get_db)):
    async with get_lock(f"resend-code:{body.email}"):
        result = await db.execute(select(User).where(User.email == body.email))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="Usuario nao encontrado")

        if user.email_verified:
            return {"status": "already_verified"}

        code = generate_otp()
        user.verification_code = code
        user.verification_expires = otp_expiry()
        await db.commit()

        asyncio.get_event_loop().run_in_executor(
            None, send_verification_email, user.email, code, user.name
        )

        return {"status": "code_sent"}


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        credits=user.credits,
        plan=user.plan,
        email_verified=user.email_verified,
    )
