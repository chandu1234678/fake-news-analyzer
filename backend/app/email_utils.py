import smtplib
import os
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(_env_path)

SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587
SMTP_USER     = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")


def generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def send_otp_email(to_email: str, otp: str) -> bool:
    if not SMTP_USER or not SMTP_PASSWORD:
        raise RuntimeError("SMTP_USER and SMTP_PASSWORD must be set in .env")

    subject = "Your FactChecker AI Reset Code"

    digit_cells = "".join([
        f"""<td style="padding:0 5px;">
              <table cellpadding="0" cellspacing="0">
                <tr><td style="
                  width:44px;height:56px;
                  background:#1e2228;
                  border:1.5px solid #2a3040;
                  border-radius:12px;
                  font-size:28px;font-weight:700;
                  color:#c0c1ff;
                  text-align:center;
                  vertical-align:middle;
                  font-family:'Courier New',monospace;
                  letter-spacing:0;
                ">{d}</td></tr>
              </table>
            </td>"""
        for d in otp
    ])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Password Reset</title>
</head>
<body style="margin:0;padding:0;background:#0d1117;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Inter',Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0d1117;padding:48px 16px;">
    <tr><td align="center">

      <!-- Card -->
      <table role="presentation" width="520" cellpadding="0" cellspacing="0"
        style="max-width:520px;width:100%;background:#161b22;border-radius:20px;
               border:1px solid #21262d;overflow:hidden;">

        <!-- Top accent bar -->
        <tr>
          <td style="height:4px;background:linear-gradient(90deg,#c0c1ff 0%,#f59e0b 50%,#6ee7b7 100%);"></td>
        </tr>

        <!-- Header -->
        <tr>
          <td style="padding:32px 40px 24px;">
            <table role="presentation" cellpadding="0" cellspacing="0">
              <tr>
                <td style="padding-right:12px;vertical-align:middle;">
                  <div style="width:40px;height:40px;background:#c0c1ff;border-radius:10px;
                              text-align:center;line-height:40px;font-size:20px;font-weight:700;color:#0d1117;">
                    ✓
                  </div>
                </td>
                <td style="vertical-align:middle;">
                  <span style="font-size:22px;font-weight:800;color:#e6edf3;letter-spacing:-0.03em;">FactChecker</span>
                  <span style="font-size:22px;font-weight:800;color:#f59e0b;letter-spacing:-0.03em;"> AI</span>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Divider -->
        <tr><td style="height:1px;background:#21262d;margin:0 40px;"></td></tr>

        <!-- Body -->
        <tr>
          <td style="padding:32px 40px;">

            <p style="margin:0 0 8px;font-size:26px;font-weight:700;color:#e6edf3;letter-spacing:-0.02em;">
              Password Reset
            </p>
            <p style="margin:0 0 28px;font-size:14px;color:#8b949e;line-height:1.7;">
              We received a request to reset your FactChecker AI password.<br>
              Use the verification code below — it expires in <strong style="color:#e6edf3;">10 minutes</strong>.
            </p>

            <!-- OTP Box -->
            <table role="presentation" cellpadding="0" cellspacing="0"
              style="background:#0d1117;border:1px solid #21262d;border-radius:14px;
                     padding:24px 20px;margin:0 0 28px;width:100%;">
              <tr>
                <td align="center">
                  <p style="margin:0 0 16px;font-size:11px;font-weight:600;color:#8b949e;
                             text-transform:uppercase;letter-spacing:0.1em;">
                    Verification Code
                  </p>
                  <table role="presentation" cellpadding="0" cellspacing="0">
                    <tr>{digit_cells}</tr>
                  </table>
                  <p style="margin:16px 0 0;font-size:12px;color:#484f58;">
                    Valid for 10 minutes · Single use only
                  </p>
                </td>
              </tr>
            </table>

            <!-- Security tip -->
            <table role="presentation" cellpadding="0" cellspacing="0"
              style="background:#1c2128;border:1px solid #21262d;border-left:3px solid #f59e0b;
                     border-radius:8px;padding:14px 16px;margin:0 0 28px;width:100%;">
              <tr>
                <td>
                  <p style="margin:0;font-size:13px;color:#8b949e;line-height:1.6;">
                    <strong style="color:#f59e0b;">🔒 Security tip:</strong>
                    Never share this code with anyone. FactChecker AI will never ask for it via chat, phone, or email.
                  </p>
                </td>
              </tr>
            </table>

            <p style="margin:0;font-size:13px;color:#484f58;line-height:1.7;">
              If you didn't request a password reset, you can safely ignore this email.
              Your account remains secure and no changes have been made.
            </p>

          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:20px 40px 28px;border-top:1px solid #21262d;background:#0d1117;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td>
                  <p style="margin:0;font-size:12px;color:#484f58;">
                    Sent by <strong style="color:#8b949e;">FactChecker AI</strong>
                    &nbsp;·&nbsp;
                    <a href="mailto:{SMTP_USER}" style="color:#484f58;text-decoration:none;">{SMTP_USER}</a>
                  </p>
                </td>
                <td align="right">
                  <p style="margin:0;font-size:11px;color:#30363d;">
                    © 2026 FactChecker AI
                  </p>
                </td>
              </tr>
            </table>
          </td>
        </tr>

      </table>
      <!-- End card -->

    </td></tr>
  </table>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"FactChecker AI <{SMTP_USER}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        raise RuntimeError(f"Failed to send email: {e}")
