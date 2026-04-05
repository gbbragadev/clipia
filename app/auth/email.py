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


def _send_otp_email(subject: str, headline: str, intro: str, to_email: str, code: str, user_name: str) -> bool:
    if not settings.SMTP_HOST:
        logger.warning("%s not configured, logging OTP for dev: %s -> %s", headline, to_email, code)
        return True

    html = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
        <h2 style="color: #7c3aed;">ClipIA</h2>
        <p>Ola, {user_name}!</p>
        <p>{intro}</p>
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
        logger.info("%s email sent to %s", headline, to_email)
        return True
    except Exception:
        logger.exception("Failed to send %s email to %s", headline.lower(), to_email)
        return False


def send_verification_email(to_email: str, code: str, user_name: str) -> bool:
    """Send OTP email via SMTP. Returns True on success."""
    subject = f"ClipIA - Seu codigo de verificacao: {code}"
    return _send_otp_email(subject, "Verification", "Seu codigo de verificacao e:", to_email, code, user_name)


def send_password_reset_email(to_email: str, code: str, user_name: str) -> bool:
    subject = f"ClipIA - Redefinir senha: {code}"
    return _send_otp_email(subject, "Password reset", "Seu codigo para redefinir a senha e:", to_email, code, user_name)


def send_account_deleted_email(to_email: str, user_name: str) -> bool:
    if not settings.SMTP_HOST:
        logger.warning("Account deleted email not configured, skipping SMTP send for %s", to_email)
        return True

    subject = "ClipIA - Confirmacao de exclusao da conta"
    html = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
        <h2 style="color: #7c3aed;">ClipIA</h2>
        <p>Ola, {user_name}!</p>
        <p>Recebemos e concluimos a solicitacao de exclusao da sua conta.</p>
        <p style="color: #6b7280; font-size: 14px;">
            Seus dados pessoais foram anonimizados, mantendo apenas os registros necessarios para integridade contabil.
        </p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText("Sua conta ClipIA foi excluida com sucesso.", "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info("Account deleted email sent to %s", to_email)
        return True
    except Exception:
        logger.exception("Failed to send account deleted email to %s", to_email)
        return False
