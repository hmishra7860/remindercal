from urllib.parse import urlparse

import httpx

from ..net_safety import assert_public_host


def _slack_payload(title: str, text: str, link: str | None) -> dict:
    body = f"*{title}*\n{text}"
    if link:
        body += f"\n<{link}|Open ReminderCal>"
    return {
        "text": f"{title}: {text}",
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": body}}],
    }


def _teams_payload(title: str, text: str, link: str | None) -> dict:
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": title, "weight": "Bolder", "size": "Medium", "wrap": True},
            {"type": "TextBlock", "text": text, "wrap": True},
        ],
    }
    if link:
        card["actions"] = [{"type": "Action.OpenUrl", "title": "Open ReminderCal", "url": link}]
    return {
        "type": "message",
        "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": card}],
    }


async def post_webhook(kind: str, url: str, title: str, text: str, link: str | None = None) -> None:
    """Push a formatted JSON payload to a Slack or Teams incoming webhook."""
    parsed = urlparse(url)
    await assert_public_host(parsed.hostname or "", parsed.port or 443)
    payload = _slack_payload(title, text, link) if kind == "slack" else _teams_payload(title, text, link)
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
