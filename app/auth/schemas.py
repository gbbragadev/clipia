import re

from pydantic import BaseModel, Field, field_validator


def _validate_password_strength(v: str) -> str:
    """Política de senha uniforme em todo o sistema (cadastro, redefinição e troca).

    Deve espelhar o que o frontend valida (frontend/src/lib/password.ts) para que
    uma senha aceita pelo UI nunca seja rejeitada pelo backend.
    """
    if len(v) < 8:
        raise ValueError("Senha deve ter no minimo 8 caracteres")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Senha deve conter pelo menos 1 letra maiuscula")
    if not re.search(r"\d", v):
        raise ValueError("Senha deve conter pelo menos 1 numero")
    return v


def _normalize_email(value) -> str:
    email = str(value).strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@") or " " in email:
        raise ValueError("invalid email")
    return email


class RegisterRequest(BaseModel):
    email: str = Field(..., description="User's email address")
    name: str = Field(..., min_length=1, max_length=255, description="Full name")
    password: str = Field(..., min_length=8, max_length=255, description="Password (min 8 chars, 1 uppercase, 1 digit)")
    referral_code: str | None = Field(default=None, max_length=12, description="Referral code from inviter")
    utm_source: str | None = Field(default=None, max_length=100)
    utm_medium: str | None = Field(default=None, max_length=100)
    utm_campaign: str | None = Field(default=None, max_length=100)
    turnstile_token: str | None = Field(
        default=None, max_length=2048, description="Cloudflare Turnstile token (anti-bot)"
    )
    consent: bool | None = Field(
        default=None,
        description="LGPD: aceite expresso dos Termos e Política de Privacidade no cadastro (registrado para auditoria).",
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value) -> str:
        return _normalize_email(value)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class LoginRequest(BaseModel):
    email: str = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value) -> str:
        return _normalize_email(value)


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type (bearer)")


class UserResponse(BaseModel):
    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    name: str = Field(..., description="User full name")
    credits: int = Field(..., description="Available credits")
    plan: str = Field(..., description="Current plan")
    email_verified: bool = Field(..., description="Email verification status")
    referral_code: str = Field(..., description="User's unique referral code")


class VerifyEmailRequest(BaseModel):
    email: str
    code: str = Field(..., min_length=6, max_length=6)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value) -> str:
        return _normalize_email(value)


class ResendCodeRequest(BaseModel):
    email: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value) -> str:
        return _normalize_email(value)


class ForgotPasswordRequest(BaseModel):
    email: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value) -> str:
        return _normalize_email(value)


class VerifyResetCodeRequest(BaseModel):
    email: str
    code: str = Field(..., min_length=6, max_length=6)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value) -> str:
        return _normalize_email(value)


class ResetPasswordRequest(BaseModel):
    reset_token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=255)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class UpdateProfileRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=255)
    new_password: str = Field(..., min_length=8, max_length=255)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class DeleteAccountRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=255)
