"""
Отправка писем через SMTP. По умолчанию и при EMAIL_DRY_RUN — только лог, без отправки.
"""

import logging
import os
import smtplib
from email.mime.text import MIMEText

from integrations.russia_validators import validate_email_basic

logger = logging.getLogger(__name__)


def _smtp_config_ok() -> bool:
    host = os.getenv("SMTP_HOST", "").strip()
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    from_addr = os.getenv("SMTP_FROM", "").strip()
    return bool(host and user and password and from_addr)


def send_email(to: str, subject: str, body: str, dry_run: bool = True) -> bool:
    """
    Отправляет письмо. Возвращает True только при реальной успешной отправке.

    Не отправляет, если dry_run=True, EMAIL_DRY_RUN=true (по умолчанию),
    или не заданы SMTP_HOST / SMTP_USER / SMTP_PASSWORD / SMTP_FROM.
    """
    if not validate_email_basic(to):
        logger.warning("Некорректный email получателя, письмо пропущено: to=%r", to)
        return False

    env_dry = os.getenv("EMAIL_DRY_RUN", "true").lower() in ("true", "1", "yes")

    if dry_run:
        logger.info("Письмо не отправлено (dry_run=True): to=%s subject=%s", to, subject)
        return False

    if env_dry:
        logger.info("Письмо не отправлено (EMAIL_DRY_RUN): to=%s subject=%s", to, subject)
        return False

    if not _smtp_config_ok():
        logger.warning(
            "SMTP не настроен (нужны SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM). "
            "Письмо не отправлено: to=%s",
            to,
        )
        return False

    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM", "").strip()

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = to

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [to], msg.as_string())
        logger.info("Письмо отправлено: to=%s subject=%s", to, subject)
        return True
    except Exception as e:
        logger.error("Ошибка отправки письма to=%s: %s", to, e)
        return False
