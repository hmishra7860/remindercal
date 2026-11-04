"""HTML + plain-text email templates."""
from html import escape


def _nl2br(text: str) -> str:
    return escape(text).replace("\n", "<br>")


def _wrap(heading: str, inner: str, footer: str) -> str:
    return f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#f4f5fb;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f5fb;padding:24px 0;">
<tr><td align="center">
<table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 2px 12px rgba(30,30,80,.08);">
<tr><td style="background:linear-gradient(135deg,#5b5bd6,#8b5cf6);padding:22px 28px;color:#fff;font-size:20px;font-weight:700;">{heading}</td></tr>
<tr><td style="padding:26px 28px;color:#25273d;font-size:15px;line-height:1.6;">{inner}</td></tr>
<tr><td style="padding:16px 28px;background:#fafaff;color:#8b8da6;font-size:12px;">{footer}</td></tr>
</table></td></tr></table></body></html>"""


def _quote(message: str | None) -> str:
    if not message:
        return ""
    return (
        '<blockquote style="margin:18px 0;padding:14px 18px;background:#fff8e1;'
        'border-left:4px solid #f5b301;border-radius:6px;color:#4a3b00;">'
        f"{_nl2br(message)}</blockquote>"
    )


def _button(url: str, label: str, color: str) -> str:
    return (
        f'<a href="{escape(url, quote=True)}" style="display:inline-block;margin:6px 8px 6px 0;padding:11px 20px;'
        f'background:{color};color:#ffffff;text-decoration:none;border-radius:8px;font-weight:600;font-size:14px;">{escape(label)}</a>'
    )


def reminder_email(*, title, description, category, when_text, custom_message, sender_name, done_url=None, snooze_url=None):
    inner = f'<div style="font-size:12px;color:#8b8da6;text-transform:uppercase;letter-spacing:.06em;">{escape(category)}</div>'
    inner += f'<h2 style="margin:4px 0 8px;font-size:22px;">{escape(title)}</h2>'
    inner += f'<div style="color:#6b6d85;">🕒 {escape(when_text)}</div>'
    if description:
        inner += f'<p style="margin:14px 0 0;">{_nl2br(description)}</p>'
    inner += _quote(custom_message)
    if done_url and snooze_url:
        inner += '<div style="margin-top:20px;">' + _button(done_url, "✔ Mark as Done", "#16a34a") + _button(snooze_url, "⏰ Snooze 1 Hour", "#5b5bd6") + "</div>"
    footer = f"Sent by {escape(sender_name)} via ReminderCal"
    html = _wrap("🔔 Reminder", inner, footer)
    text = f"Reminder: {title}\nWhen: {when_text}\nCategory: {category}\n"
    if description:
        text += f"\n{description}\n"
    if custom_message:
        text += f"\n> {custom_message}\n"
    if done_url and snooze_url:
        text += f"\nMark as done: {done_url}\nSnooze 1 hour: {snooze_url}\n"
    text += f"\n-- Sent by {sender_name} via ReminderCal"
    return html, text


def birthday_email(*, name, age, custom_message, sender_name):
    inner = f'<div style="text-align:center;font-size:48px;">🎂🎉</div>'
    inner += f'<h2 style="text-align:center;margin:6px 0 4px;font-size:26px;">Happy Birthday, {escape(name)}!</h2>'
    if age:
        inner += f'<p style="text-align:center;color:#6b6d85;margin:0;">Wishing you a wonderful {age}th year ahead.</p>'.replace(
            f"{age}th", _ordinal(age)
        )
    inner += _quote(custom_message)
    inner += f'<p style="margin-top:22px;">Warm wishes,<br><strong>{escape(sender_name)}</strong></p>'
    html = _wrap("🎈 Birthday Wishes", inner, f"Sent personally by {escape(sender_name)}")
    text = f"Happy Birthday, {name}!\n"
    if age:
        text += f"Wishing you a wonderful {_ordinal(age)} year ahead.\n"
    if custom_message:
        text += f"\n{custom_message}\n"
    text += f"\nWarm wishes,\n{sender_name}"
    return html, text


def digest_email(*, name, reminders, birthdays):
    inner = f"<p>Good morning {escape(name)}, here's your day:</p>"
    if reminders:
        inner += "<h3 style='margin:16px 0 6px;'>🔔 Today's reminders</h3><ul>" + "".join(f"<li>{escape(x)}</li>" for x in reminders) + "</ul>"
    if birthdays:
        inner += "<h3 style='margin:16px 0 6px;'>🎂 Upcoming birthdays</h3><ul>" + "".join(f"<li>{escape(x)}</li>" for x in birthdays) + "</ul>"
    html = _wrap("☀️ Daily Digest", inner, "ReminderCal daily digest")
    text = f"Daily digest for {name}\n"
    if reminders:
        text += "\nToday's reminders:\n" + "\n".join(f"- {x}" for x in reminders) + "\n"
    if birthdays:
        text += "\nUpcoming birthdays:\n" + "\n".join(f"- {x}" for x in birthdays) + "\n"
    return html, text


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
