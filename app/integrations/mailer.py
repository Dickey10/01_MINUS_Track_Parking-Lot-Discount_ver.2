import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from app.config import settings


def _send_message(subject: str, body: str, recipients: list[str]) -> bool:
    if not settings.smtp_user or not settings.smtp_password or not recipients:
        return False

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_user
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)
    return True


async def send_result_email(application: dict, recipients: list[str]) -> bool:
    status_label = "SUCCESS" if application["status"] in ("succeeded", "manual") else "FAILED"
    subject = f"[Parking Discount {status_label}] {application['car_number']}"
    body = "\n".join(
        [
            f"Status: {application['status']}",
            f"Car number: {application['car_number']}",
            f"Department: {application['dept']}",
            f"Requester: {application['requester']}",
            f"Visitor company: {application.get('visitor_company', '')}",
            f"Visit purpose: {application['visit_purpose']}",
            f"Entry time: {application['entry_time']}",
            f"Effective minutes: {application['effective_minutes']}",
            f"60-minute coupons: {application['coupon_60_count']}",
            f"30-minute coupons: {application['coupon_30_count']}",
            f"Failure reason: {application.get('failure_reason', '')}",
            f"Screenshot: {application.get('screenshot_path', '')}",
        ]
    )
    try:
        return _send_message(subject, body, recipients)
    except Exception as exc:
        print(f"[mailer] result email failed: {exc}")
        return False


async def send_failure_alert(req, error_msg: str, screenshot_path: str) -> None:
    recipients = [email.strip() for email in settings.alert_email.split(",") if email.strip()]
    if not recipients:
        return

    screenshot_note = screenshot_path if screenshot_path and Path(screenshot_path).exists() else ""
    body = "\n".join(
        [
            f"Car number: {req.car_number}",
            f"60-minute coupons: {getattr(req, 'coupon_60_count', 0)}",
            f"30-minute coupons: {getattr(req, 'coupon_30_count', 0)}",
            f"Department: {req.dept}",
            f"Requester: {req.requester}",
            f"Error: {error_msg}",
            f"Screenshot: {screenshot_note}",
        ]
    )
    try:
        _send_message(f"[Parking Discount Failed] {req.car_number}", body, recipients)
    except Exception as exc:
        print(f"[mailer] failure alert failed: {exc}")

