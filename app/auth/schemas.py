from pydantic import BaseModel, Field, field_validator


def _normalize_email(value) -> str:
    email = str(value).strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@") or " " in email:
        raise ValueError("invalid email")
    return email


class RegisterRequest(BaseModel):
    email: str = Field(..., description="User's email address")
    name: str = Field(..., min_length=1, max_length=255, description="Full name")
    password: str = Field(..., min_length=6, max_length=255, description="Password (min 6 chars)")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value) -> str:
        return _normalize_email(value)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


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
    new_password: str = Field(..., min_length=6, max_length=255)


class UpdateProfileRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=255)
    new_password: str = Field(..., min_length=6, max_length=255)


class DeleteAccountRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=255)
