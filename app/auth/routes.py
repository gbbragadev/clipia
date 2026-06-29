import asyncio
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.disposable import is_disposable_email
from app.auth.email import (
    generate_otp,
    otp_expiry,
    send_account_deleted_email,
    send_password_reset_email,
    send_verification_email,
)
from app.auth.schemas import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResendCodeRequest,
    ResetPasswordRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
    VerifyEmailRequest,
    VerifyResetCodeRequest,
)
from app.auth.service import create_access_token, create_reset_token, decode_reset_token, hash_password, verify_password
from app.config import settings
from app.db.engine import get_db
from app.db.models import CreditPurchase, Job, User
from app.observability import record_credit_metric
from app.utils.locks import get_lock
from app.utils.ratelimit import client_ip

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=client_ip)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Creates a new user account.",
    responses={201: {"description": "User created"}, 409: {"description": "Email already exists"}},
)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def register(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user and return an access token."""
    if is_disposable_email(body.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use um email permanente; provedores descartaveis nao sao aceitos.",
        )
    async with get_lock(f"register:{body.email}"):
        result = await db.execute(select(User).where(User.email == body.email))
        if result.scalar_one_or_none() is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email ja cadastrado")

        # Resolve referrer if referral code provided
        referrer_id = None
        if body.referral_code:
            ref_result = await db.execute(select(User).where(User.referral_code == body.referral_code))
            referrer = ref_result.scalar_one_or_none()
            if referrer:
                referrer_id = referrer.id

        code = generate_otp()
        user = User(
            email=body.email,
            name=body.name,
            password_hash=hash_password(body.password),
            credits=0,
            email_verified=False,
            verification_code=code,
            verification_expires=otp_expiry(),
            utm_source=body.utm_source,
            utm_medium=body.utm_medium,
            utm_campaign=body.utm_campaign,
            referral_code=uuid.uuid4().hex[:8],
            referred_by=referrer_id,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        await asyncio.to_thread(send_verification_email, body.email, code, body.name)

        token = create_access_token(str(user.id))
        return TokenResponse(access_token=token)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User login",
    description="Authenticates user and returns JWT token.",
    responses={200: {"description": "Login successful"}, 401: {"description": "Invalid credentials"}},
)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate user."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou senha incorretos")

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.post(
    "/verify-email",
    summary="Verify email",
    description="Verifies a user's email using OTP.",
    responses={
        200: {"description": "Email verified"},
        400: {"description": "Invalid code"},
        404: {"description": "User not found"},
    },
)
@limiter.limit("5/minute")
async def verify_email(request: Request, body: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    """Verify email using OTP."""
    async with get_lock(f"verify-email:{body.email}"):
        result = await db.execute(select(User).where(User.email == body.email))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="Usuario nao encontrado")

        if user.email_verified:
            return {"status": "already_verified"}

        MAX_OTP_ATTEMPTS = 5

        if user.otp_attempts >= MAX_OTP_ATTEMPTS:
            raise HTTPException(status_code=429, detail="Muitas tentativas. Solicite um novo codigo.")

        if not user.verification_code or not user.verification_expires:
            raise HTTPException(status_code=400, detail="Nenhum codigo pendente")

        if datetime.now(timezone.utc) > _ensure_utc(user.verification_expires):
            raise HTTPException(status_code=400, detail="Codigo expirado. Solicite um novo.")

        if user.verification_code != body.code:
            user.otp_attempts += 1
            await db.commit()
            remaining = MAX_OTP_ATTEMPTS - user.otp_attempts
            if remaining <= 0:
                raise HTTPException(status_code=429, detail="Muitas tentativas. Solicite um novo codigo.")
            raise HTTPException(status_code=400, detail=f"Codigo incorreto. {remaining} tentativa(s) restante(s).")

        user.email_verified = True
        user.otp_attempts = 0
        user.verification_code = None
        user.verification_expires = None
        user.credits = 2
        await db.commit()
        record_credit_metric("credit", 2)

        # Credit referrer with 2 bonus credits (max 10 referrals per user)
        MAX_REFERRAL_BONUS_COUNT = 10

        if user.referred_by:
            from sqlalchemy import func as sqla_func
            from sqlalchemy import update as sql_update

            # Count how many verified referrals already credited
            referral_count = (
                await db.execute(
                    select(sqla_func.count(User.id)).where(
                        User.referred_by == user.referred_by, User.email_verified.is_(True)
                    )
                )
            ).scalar() or 0

            if referral_count <= MAX_REFERRAL_BONUS_COUNT:
                await db.execute(sql_update(User).where(User.id == user.referred_by).values(credits=User.credits + 2))
                await db.commit()
                record_credit_metric("referral_bonus", 2)

        return {"status": "verified", "credits": 2}


@router.post(
    "/resend-code",
    summary="Resend OTP",
    description="Resends the verification email code.",
    responses={200: {"description": "Code sent"}},
)
@limiter.limit("3/minute")
async def resend_code(request: Request, body: ResendCodeRequest, db: AsyncSession = Depends(get_db)):
    """Resend email verification code."""
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
        user.otp_attempts = 0
        await db.commit()

        await asyncio.to_thread(send_verification_email, user.email, code, user.name)

        return {"status": "code_sent"}


@router.post(
    "/forgot-password",
    summary="Forgot password",
    description="Sends an OTP to reset password.",
    responses={200: {"description": "OTP sent"}},
)
@limiter.limit("3/minute")
async def forgot_password(request: Request, body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Initiate password reset process."""
    async with get_lock(f"forgot-password:{body.email}"):
        result = await db.execute(select(User).where(User.email == body.email))
        user = result.scalar_one_or_none()

        if user is not None:
            code = generate_otp()
            user.verification_code = code
            user.verification_expires = otp_expiry()
            user.otp_attempts = 0
            await db.commit()

            await asyncio.to_thread(send_password_reset_email, user.email, code, user.name)

    return {"status": "code_sent"}


@router.post(
    "/verify-reset-code",
    summary="Verify password reset code",
    description="Verifies the OTP to reset password.",
    responses={200: {"description": "OTP verified"}},
)
@limiter.limit("5/minute")
async def verify_reset_code(request: Request, body: VerifyResetCodeRequest, db: AsyncSession = Depends(get_db)):
    """Verify OTP for password reset."""
    async with get_lock(f"verify-reset-code:{body.email}"):
        result = await db.execute(select(User).where(User.email == body.email))
        user = result.scalar_one_or_none()

        if not user or not user.verification_code or not user.verification_expires:
            raise HTTPException(status_code=400, detail="Codigo incorreto")

        MAX_OTP_ATTEMPTS = 5

        if user.otp_attempts >= MAX_OTP_ATTEMPTS:
            raise HTTPException(status_code=429, detail="Muitas tentativas. Solicite um novo codigo.")

        if datetime.now(timezone.utc) > _ensure_utc(user.verification_expires):
            raise HTTPException(status_code=400, detail="Codigo expirado. Solicite um novo.")

        if user.verification_code != body.code:
            user.otp_attempts += 1
            await db.commit()
            remaining = MAX_OTP_ATTEMPTS - user.otp_attempts
            if remaining <= 0:
                raise HTTPException(status_code=429, detail="Muitas tentativas. Solicite um novo codigo.")
            raise HTTPException(status_code=400, detail=f"Codigo incorreto. {remaining} tentativa(s) restante(s).")

        user.otp_attempts = 0
        await db.commit()

        return {"status": "verified", "reset_token": create_reset_token(str(user.id))}


@router.post(
    "/reset-password",
    summary="Reset password",
    description="Resets the password using a token.",
    responses={200: {"description": "Password reset"}},
)
@limiter.limit("3/minute")
async def reset_password(request: Request, body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Finalize password reset."""
    payload = decode_reset_token(body.reset_token)
    if not payload:
        raise HTTPException(status_code=400, detail="Token de redefinicao invalido ou expirado")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=400, detail="Token de redefinicao invalido ou expirado")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Token de redefinicao invalido ou expirado")

    # Invalidate token if already used
    token_iat = payload.get("iat")
    if token_iat and user.password_reset_at:
        token_time = datetime.fromtimestamp(token_iat, tz=timezone.utc)
        if token_time < user.password_reset_at:
            raise HTTPException(status_code=400, detail="Token de redefinicao invalido ou expirado")

    user.password_hash = hash_password(body.new_password)
    user.verification_code = None
    user.verification_expires = None
    user.password_reset_at = datetime.now(timezone.utc)
    await db.commit()

    return {"status": "password_reset"}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Returns the authenticated user's details.",
    responses={200: {"description": "User details"}},
)
async def get_me(user: User = Depends(get_current_user)):
    """Retrieve user profile."""
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        credits=user.credits,
        plan=user.plan,
        email_verified=user.email_verified,
        referral_code=user.referral_code,
    )


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update profile",
    description="Updates user profile.",
    responses={200: {"description": "Profile updated"}},
)
async def update_me(
    body: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user information."""
    user.name = body.name
    await db.commit()
    await db.refresh(user)
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        credits=user.credits,
        plan=user.plan,
        email_verified=user.email_verified,
        referral_code=user.referral_code,
    )


@router.post(
    "/change-password",
    summary="Change password",
    description="Changes current authenticated user password.",
    responses={200: {"description": "Password changed"}},
)
async def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change user password."""
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Senha atual incorreta")

    user.password_hash = hash_password(body.new_password)
    await db.commit()
    return {"status": "password_changed"}


@router.post(
    "/delete-account",
    summary="Delete account",
    description="Permanently deletes the user's account.",
    responses={200: {"description": "Account deleted"}},
)
async def delete_account(
    body: DeleteAccountRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete user account."""
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Senha incorreta")

    original_email = user.email
    original_name = user.name

    user.name = "Deleted User"
    user.email = f"deleted_{user.id.hex}@removed.clipia.com.br"
    user.plan = "deleted"
    user.credits = 0
    user.email_verified = False
    user.verification_code = None
    user.verification_expires = None
    user.password_hash = hash_password(secrets.token_urlsafe(32))
    await db.commit()

    await asyncio.to_thread(send_account_deleted_email, original_email, original_name)
    return {"status": "account_deleted"}


@router.get(
    "/export-data",
    summary="Export data",
    description="Exports all user data.",
    responses={200: {"description": "Exported data payload"}},
)
async def export_data(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export user data to JSON."""
    jobs_result = await db.execute(select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc()))
    purchases_result = await db.execute(
        select(CreditPurchase).where(CreditPurchase.user_id == user.id).order_by(CreditPurchase.created_at.desc())
    )
    jobs = jobs_result.scalars().all()
    purchases = purchases_result.scalars().all()

    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "credits": user.credits,
            "plan": user.plan,
            "email_verified": user.email_verified,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "jobs": [
            {
                "id": str(job.id),
                "topic": job.topic,
                "style": job.style,
                "status": job.status,
                "duration_target": job.duration_target,
                "current_step": job.current_step,
                "error": job.error,
                "video_url": job.video_url,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "exported_at": job.exported_at.isoformat() if job.exported_at else None,
            }
            for job in jobs
        ],
        "purchases": [
            {
                "id": str(purchase.id),
                "package_name": purchase.package_name,
                "credits_amount": purchase.credits_amount,
                "price_brl": purchase.price_brl,
                "status": purchase.status,
                "mp_payment_id": purchase.mp_payment_id,
                "mp_preference_id": purchase.mp_preference_id,
                "created_at": purchase.created_at.isoformat() if purchase.created_at else None,
                "paid_at": purchase.paid_at.isoformat() if purchase.paid_at else None,
            }
            for purchase in purchases
        ],
    }
