"""Письмо подтверждения адреса."""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from app.core import mailer
from app.core.config import get_settings


async def test_without_smtp_link_goes_to_log(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger='app.core.mailer')
    await mailer.send_verification('a@example.com', 'tok123')
    assert '/verify/tok123' in caplog.text


async def test_with_smtp_message_is_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), 'smtp_host', 'mail.local')
    with patch.object(mailer, '_send') as send:
        await mailer.send_verification('b@example.com', 'tok456')
    msg = send.call_args.args[0]
    assert msg['To'] == 'b@example.com'
    assert '/verify/tok456' in msg.get_content()


async def test_smtp_failure_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), 'smtp_host', 'mail.local')
    with patch.object(mailer, '_send', side_effect=OSError('down')):
        await mailer.send_verification('c@example.com', 'tok789')
