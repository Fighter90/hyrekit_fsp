"""Отправка писем: подтверждение адреса при регистрации (ТЗ 2.2, п. 4).

Если SMTP не настроен, письмо не уходит, а ссылка подтверждения пишется в лог —
так демо и тесты работают без почтового сервера. В docker-compose поднят
Mailpit: письма видны в веб-интерфейсе http://localhost:8025.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def verification_link(token: str) -> str:
    return f'{get_settings().public_url.rstrip("/")}/verify/{token}'


def _send(msg: EmailMessage) -> None:
    s = get_settings()
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10) as smtp:
        if s.smtp_tls:
            smtp.starttls()
        if s.smtp_user:
            smtp.login(s.smtp_user, s.smtp_password)
        smtp.send_message(msg)


async def send_verification(email: str, token: str) -> None:
    """Письмо со ссылкой подтверждения. Ошибка почты не ломает регистрацию."""
    link = verification_link(token)
    s = get_settings()
    if not s.smtp_host:
        logger.info('SMTP не настроен, ссылка подтверждения для %s: %s', email, link)
        return
    msg = EmailMessage()
    msg['From'] = s.mail_from
    msg['To'] = email
    msg['Subject'] = 'HyreKit: подтвердите адрес почты'
    msg.set_content(
        'Здравствуйте!\n\nПодтвердите адрес, чтобы работодатели могли увидеть ваш профиль,\n'
        f'а приглашения приходили на эту почту:\n\n{link}\n\nЕсли вы не регистрировались в HyreKit, '
        'просто проигнорируйте письмо.\n'
    )
    try:
        await asyncio.to_thread(_send, msg)
    except (OSError, smtplib.SMTPException):
        logger.warning('Не удалось отправить письмо подтверждения на %s', email, exc_info=True)
