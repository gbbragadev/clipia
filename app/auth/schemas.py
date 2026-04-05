from pydantic import BaseModel, Field, field_validator


class RegisterRequest(BaseModel):
    email: str
    name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=6, max_length=255)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value) -> str:
        email = str(value).strip().lower()
        if "@" not in email or email.startswith("@") or email.endswith("@") or " " in email:
            raise ValueError("invalid email")
        return email

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value) -> str:
        email = str(value).strip().lower()
        if "@" not in email or email.startswith("@") or email.endswith("@") or " " in email:
            raise ValueError("invalid email")
        return email


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    credits: int
    plan: str
    email_verified: bool


class VerifyEmailRequest(BaseModel):
    email: str
    code: str = Field(..., min_length=6, max_length=6)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value) -> str:
        email = str(value).strip().lower()
        if "@" not in email or email.startswith("@") or email.endswith("@") or " " in email:
            raise ValueError("invalid email")
        return email


class ResendCodeRequest(BaseModel):
    email: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value) -> str:
        email = str(value).strip().lower()
        if "@" not in email or email.startswith("@") or email.endswith("@") or " " in email:
            raise ValueError("invalid email")
        return email
