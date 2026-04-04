import logging
import random
import smtplib
import string
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger(__name__)


def generate_otp() -> str:
    """Generate 6-digit numeric OTP."""
    return "".join(random.choices(string.digits, k=6))


def otp_expiry() -> datetime:
    """OTP valid for 10 minutes."""
    return datetime.now(timezone.utc) + timedelta(minutes=10)


def send_verification_email(to_email: str, code: str, user_name: str) -> bool:
    """Send OTP email via SMTP. Returns True on success."""
    if not settings.SMTP_HOST:
        logger.warning("SMTP not configured, logging OTP for dev: %s -> %s", to_email, code)
        return True

    subject = f"ClipIA - Seu codigo de verificacao: {code}"
    html = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
        <h2 style="color: #7c3aed;">ClipIA</h2>
        <p>Ola, {user_name}!</p>
        <p>Seu codigo de verificacao e:</p>
        <div style="background: #f3f4f6; border-radius: 8px; padding: 20px; text-align: center; margin: 24px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #1f2937;">{code}</span>
        </div>
        <p style="color: #6b7280; font-size: 14px;">Este codigo expira em 10 minutos.</p>
        <p style="color: #6b7280; font-size: 14px;">Se voce nao solicitou este codigo, ignore este email.</p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(f"Seu codigo ClipIA: {code} (expira em 10 min)", "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info("Verification email sent to %s", to_email)
        return True
    except Exception:
        logger.exception("Failed to send verification email to %s", to_email)
        return False
