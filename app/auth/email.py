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


def send_welcome_email(to_email: str, user_name: str, credits: int) -> bool:
    """Boas-vindas pos-verificacao: creditos, canais de suporte e convite a feedback.

    Fire-and-forget (rodar via BackgroundTasks): nunca levanta excecao, so loga falha.
    """
    if not settings.SMTP_HOST:
        logger.info("Welcome email skipped (SMTP not configured) for %s", to_email)
        return True

    support_email = settings.SUPPORT_EMAIL
    whatsapp_html = ""
    if settings.SUPPORT_WHATSAPP:
        whatsapp_html = (
            f'<p style="margin: 4px 0;">WhatsApp: '
            f'<a href="https://wa.me/{settings.SUPPORT_WHATSAPP}" style="color: #ff5638;">falar com a gente</a></p>'
        )

    subject = "Bem-vindo ao ClipIA! Seus creditos ja estao na conta"
    html = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
        <h2 style="color: #ff5638;">ClipIA</h2>
        <p>Ola, {user_name}!</p>
        <p>Sua conta esta verificada e voce ja tem <strong>{credits} creditos</strong> para criar seus primeiros videos.</p>
        <div style="text-align: center; margin: 24px 0;">
            <a href="{settings.FRONTEND_URL}/dashboard"
               style="background: #ff5638; color: #fff; padding: 12px 28px; border-radius: 8px; text-decoration: none; font-weight: bold;">
                Criar meu primeiro video
            </a>
        </div>
        <p style="color: #6b7280; font-size: 14px;">
            Estamos em beta e sua opiniao molda o produto: responda este email com qualquer
            sugestao ou problema — a resposta cai direto na nossa caixa de suporte.
        </p>
        <div style="color: #6b7280; font-size: 14px; border-top: 1px solid #e5e7eb; padding-top: 16px; margin-top: 16px;">
            <p style="margin: 4px 0;">Suporte: <a href="mailto:{support_email}" style="color: #ff5638;">{support_email}</a></p>
            {whatsapp_html}
        </div>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email
    msg["Reply-To"] = support_email
    msg.attach(
        MIMEText(
            f"Bem-vindo ao ClipIA! Voce tem {credits} creditos. Suporte: {support_email}",
            "plain",
        )
    )
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info("Welcome email sent to %s", to_email)
        return True
    except Exception:
        logger.exception("Failed to send welcome email to %s", to_email)
        return False


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
