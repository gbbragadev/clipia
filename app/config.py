from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # API Keys
    ANTHROPIC_API_KEY: str = ""
    PEXELS_API_KEY: str = ""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://clipia:clipia_dev@localhost:5435/clipia"

    # Auth
    JWT_SECRET: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Redis
    REDIS_URL: str = "redis://localhost:6382/0"

    # Paths
    STORAGE_DIR: Path = BASE_DIR / "storage"
    REFERENCE_VOICE: Path = BASE_DIR / "reference_voices" / "narrator_ptbr.wav"
    FONT_PATH: Path = BASE_DIR / "fonts" / "Montserrat-Bold.ttf"

    # Video
    VIDEO_WIDTH: int = 1080
    VIDEO_HEIGHT: int = 1920
    VIDEO_FPS: int = 30

    # GPU
    DEVICE: str = "cuda"
    WHISPER_MODEL_SIZE: str = "large-v3"
    WHISPER_COMPUTE_TYPE: str = "float16"

    # Claude
    CLAUDE_MODEL: str = "claude-sonnet-4-6"

    # MercadoPago
    MP_ACCESS_TOKEN: str = ""
    MP_WEBHOOK_SECRET: str = ""
    FRONTEND_URL: str = "http://localhost:3003"
    BACKEND_URL: str = ""  # https://api.clipia.com.br in production

    # Rate Limiting
    RATE_LIMIT_AUTH: str = "5/minute"
    RATE_LIMIT_GENERATE: str = "10/minute"
    RATE_LIMIT_DEFAULT: str = "60/minute"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3003"  # comma-separated, "*" for dev

    # SMTP (email verification)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@clipia.com.br"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
