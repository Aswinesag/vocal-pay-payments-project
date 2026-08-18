"""Asynchronous email delivery for security notifications."""

from __future__ import annotations

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

import aiosmtplib
from loguru import logger

from app.core.config import settings


class EmailServiceError(Exception):
    """Raised when email delivery fails."""


async def _send_message(message: MIMEMultipart) -> None:
    """Deliver a message using the configured encrypted SMTP transport."""
    implicit_tls = settings.SMTP_USE_TLS and settings.SMTP_PORT == 465
    await aiosmtplib.send(
        message,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USERNAME,
        password=settings.SMTP_PASSWORD,
        use_tls=implicit_tls,
        start_tls=settings.SMTP_USE_TLS and not implicit_tls,
        timeout=10,
    )


async def send_otp_email(
    recipient_email: str,
    recipient_name: str,
    otp_code: str,
    amount: float,
    expires_minutes: int = 5,
) -> bool:
    """Send a transaction verification code to a registered email address."""
    message = MIMEMultipart("alternative")
    message["Subject"] = "VocalPay - Transaction Verification Required"
    message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    message["To"] = recipient_email

    text_body = f"""
VocalPay Security Verification

Hello {recipient_name},

Transaction Amount: INR {amount:.2f}
Verification Code: {otp_code}

This code expires in {expires_minutes} minutes.

If you did not initiate this transaction, contact support immediately.

VocalPay Security Team
    """.strip()
    html_body = f"""<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;color:#333"><div style="max-width:600px;margin:0 auto;padding:20px"><h1>VocalPay Security</h1><p>Hello <strong>{escape(recipient_name)}</strong>,</p><p>A transaction verification is required for your VocalPay account.</p><p><strong>Transaction Amount:</strong> INR {amount:.2f}</p><div style="border:2px solid #667eea;padding:20px;text-align:center"><p>Your verification code:</p><div style="font-size:32px;font-weight:bold;letter-spacing:8px">{otp_code}</div><p>Expires in {expires_minutes} minutes</p></div><p><strong>Security Notice:</strong> If you did not initiate this transaction, contact VocalPay support immediately.</p></div></body></html>"""
    message.attach(MIMEText(text_body, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        await _send_message(message)
    except Exception as exc:
        logger.bind(error=str(exc)).error("Failed to deliver OTP email")
        raise EmailServiceError("OTP email delivery failed.") from exc

    logger.bind(amount=amount).info("OTP email delivered successfully")
    return True


async def send_transaction_alert(
    recipient_email: str,
    recipient_name: str,
    transaction_id: str,
    amount: float,
    status: str,
) -> bool:
    """Send a transaction status notification."""
    message = MIMEMultipart("alternative")
    message["Subject"] = f"VocalPay - Transaction {status}"
    message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    message["To"] = recipient_email
    html_body = f"""<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;padding:20px"><h2>Transaction {escape(status)}</h2><p>Hello {escape(recipient_name)},</p><p><strong>Amount:</strong> INR {amount:.2f}<br><strong>Status:</strong> {escape(status)}<br><strong>ID:</strong> {escape(transaction_id)}</p></body></html>"""
    message.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        await _send_message(message)
    except Exception as exc:
        logger.bind(error=str(exc)).error("Failed to deliver transaction alert")
        raise EmailServiceError("Transaction alert delivery failed.") from exc

    logger.bind(transaction_id=transaction_id).info("Transaction alert delivered")
    return True


__all__ = ("send_otp_email", "send_transaction_alert", "EmailServiceError")
