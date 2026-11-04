from email.message import EmailMessage
from email.utils import formataddr

import aiosmtplib

from ..models import User
from ..net_safety import UnsafeTarget, assert_public_host
from ..security import decrypt_secret


class SMTPNotConfigured(RuntimeError):
    pass


async def send_email(user: User, to_email: str, subject: str, html_body: str, text_body: str) -> None:
    """Send through the *user's own* SMTP server (BYO-SMTP)."""
    if not (user.smtp_host and user.smtp_port and user.smtp_user and user.smtp_pass):
        raise SMTPNotConfigured("SMTP is not configured. Add your SMTP credentials in Settings.")

    try:
        await assert_public_host(user.smtp_host, user.smtp_port)
    except UnsafeTarget as exc:
        raise SMTPNotConfigured(str(exc)) from exc

    from_addr = user.from_email or user.smtp_user
    msg = EmailMessage()
    msg["From"] = formataddr((user.full_name, from_addr))
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Reply-To"] = from_addr
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    port = int(user.smtp_port)
    await aiosmtplib.send(
        msg,
        hostname=user.smtp_host,
        port=port,
        username=user.smtp_user,
        password=decrypt_secret(user.smtp_pass),
        use_tls=(port == 465),  # implicit TLS
        start_tls=None if port != 465 else False,  # STARTTLS when offered (587/25)
        timeout=20,
    )
