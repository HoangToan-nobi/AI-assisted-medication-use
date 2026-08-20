"""Provider-neutral SMTP adapter for transactional auth email."""
import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from src.config import get_settings

logger = logging.getLogger(__name__)


def _send(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from:
        if settings.app_env == "production":
            raise RuntimeError("SMTP chua duoc cau hinh")
        logger.warning("SMTP not configured. Auth email for %s:\n%s", to, body)
        return
    message = EmailMessage()
    message["From"] = (
        formataddr((settings.smtp_from_name, settings.smtp_from))
        if settings.smtp_from_name
        else settings.smtp_from
    )
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def send_verification_email(email: str, token: str) -> None:
    url = f"{get_settings().frontend_url.rstrip('/')}/auth/verify-email?token={token}"
    _send(email, "Xác minh tài khoản MediCheck", f"Mở liên kết sau trong 24 giờ để xác minh email:\n\n{url}")


def send_password_reset_email(email: str, token: str) -> None:
    url = f"{get_settings().frontend_url.rstrip('/')}/auth/reset-password?token={token}"
    _send(email, "Đặt lại mật khẩu MediCheck", f"Mở liên kết sau trong 30 phút để đặt lại mật khẩu:\n\n{url}")


def send_pharmacist_decision_email(email: str, approved: bool, reason: str | None = None) -> None:
    if approved:
        body = "Hồ sơ dược sĩ MediCheck của bạn đã được duyệt. Bạn có thể đăng nhập ngay."
    else:
        body = "Yêu cầu vai trò dược sĩ chưa được duyệt. Tài khoản đã được chuyển sang người dùng."
        if reason:
            body += f"\n\nLý do: {reason}"
    _send(email, "Kết quả xét duyệt tài khoản MediCheck", body)
