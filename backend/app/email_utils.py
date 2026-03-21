import os
import random
import string
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(_env_path)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASSWORD", "")

logger = logging.getLogger(__name__)


def generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def send_otp_email(to_email: str, otp: str) -> bool:
    if not SMTP_USER or not SMTP_PASS:
        raise RuntimeError("SMTP credentials not configured.")

    digits = "".join([
        f'<td style="padding:0 4px;">'
        f'<div style="width:48px;height:60px;background:#0d1117;border:2px solid #30363d;'
        f'border-radius:10px;font-size:30px;font-weight:700;color:#c0c1ff;'
        f'text-align:center;line-height:60px;font-family:monospace;">{d}</div></td>'
        for d in otp
    ])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Reset your password</title></head>
<body style="margin:0;padding:0;background:#090c10;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#090c10;padding:40px 16px;">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0"
  style="max-width:560px;width:100%;background:#0d1117;border-radius:16px;border:1px solid #21262d;overflow:hidden;">
  <tr><td style="height:3px;background:linear-gradient(90deg,#818cf8,#c0c1ff 40%,#f59e0b 70%,#6ee7b7);"></td></tr>
  <tr>
    <td style="padding:32px 40px 24px;">
      <span style="font-size:20px;font-weight:800;color:#e6edf3;">FactChecker</span>
      <span style="font-size:20px;font-weight:800;color:#f59e0b;"> AI</span>
    </td>
  </tr>
  <tr><td style="height:1px;background:#21262d;"></td></tr>
  <tr>
    <td style="padding:32px 40px 28px;">
      <p style="margin:0 0 6px;font-size:24px;font-weight:700;color:#e6edf3;">Reset your password</p>
      <p style="margin:0 0 28px;font-size:14px;color:#8b949e;line-height:1.7;">
        Enter the code below — it expires in <strong style="color:#c0c1ff;">10 minutes</strong>.
      </p>
      <table width="100%" cellpadding="0" cellspacing="0"
        style="background:#161b22;border:1px solid #30363d;border-radius:12px;padding:28px 20px;margin-bottom:28px;">
        <tr>
          <td align="center">
            <p style="margin:0 0 18px;font-size:11px;font-weight:600;color:#6e7681;text-transform:uppercase;letter-spacing:0.12em;">Verification Code</p>
            <table cellpadding="0" cellspacing="0"><tr>{digits}</tr></table>
            <p style="margin:18px 0 0;font-size:12px;color:#484f58;">Valid for 10 minutes · Single use only</p>
          </td>
        </tr>
      </table>
      <table width="100%" cellpadding="0" cellspacing="0"
        style="background:#161b22;border-left:3px solid #f59e0b;border-radius:8px;padding:14px 18px;margin-bottom:28px;">
        <tr><td>
          <p style="margin:0;font-size:13px;color:#8b949e;">
            <strong style="color:#f59e0b;">Security notice:</strong> Never share this code.
          </p>
        </td></tr>
      </table>
      <p style="margin:0;font-size:13px;color:#484f58;">Didn't request this? You can safely ignore this email.</p>
    </td>
  </tr>
  <tr>
    <td style="padding:18px 40px 24px;border-top:1px solid #21262d;background:#090c10;">
      <p style="margin:0;font-size:12px;color:#484f58;">Sent by <strong style="color:#6e7681;">FactChecker AI</strong></p>
    </td>
  </tr>
</table>
</td></tr>
</table>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Your verification code is {otp}"
    msg["From"]    = f"FactChecker AI <{SMTP_USER}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(html, "html"))

    # Gmail SMTP via port 587 + STARTTLS
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, to_email, msg.as_string())

    logger.info("OTP email sent via SMTP to %s", to_email)
    return True
