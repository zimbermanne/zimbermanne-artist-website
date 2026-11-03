"""Optional email through Resend. Every function is a no-op when RESEND_API_KEY is not set."""
import httpx

from . import config


def send_email(to: str, subject: str, text: str, reply_to: str | None = None) -> bool:
    if not (config.RESEND_API_KEY and config.CONTACT_FROM):
        return False
    payload = {"from": config.CONTACT_FROM, "to": [to], "subject": subject, "text": text}
    if reply_to:
        payload["reply_to"] = reply_to
    try:
        r = httpx.post(
            "https://api.resend.com/emails", json=payload, timeout=10,
            headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
        )
        return r.status_code < 300
    except httpx.HTTPError:
        return False
