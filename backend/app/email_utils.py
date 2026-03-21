import os
import random
import string
import logging
import requests
from dotenv import load_dotenv

_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(_env_path)

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
FROM_EMAIL    = os.getenv("SMTP_USER", "bc833498@gmail.com")
FROM_NAME     = "FactChecker AI"

logger = logging.getLogger(__name__)


def generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def send_otp_email(to_email: str, otp: str) -> bool:
    if not BREVO_API_KEY:
        raise RuntimeError("BREVO_API_KEY is not configured.")

    digits = "".join([
        f'<td style="padding:0 5px;">'
        f'<div style="width:52px;height:64px;background:#1c2333;border:2px solid #3d4663;'
        f'border-radius:12px;font-size:32px;font-weight:700;color:#ffffff;'
        f'text-align:center;line-height:64px;font-family:\'Courier New\',monospace;">{d}</div></td>'
        for d in otp
    ])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Password Reset</title>
</head>
<body style="margin:0;padding:0;background:#0f1117;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0f1117;padding:32px 16px;">
    <tr><td align="center">
      <table width="480" cellpadding="0" cellspacing="0"
        style="max-width:480px;width:100%;background:#161b27;border-radius:20px;
               border:1px solid #2a3147;overflow:hidden;">

        <!-- Header -->
        <tr>
          <td style="padding:28px 32px 20px;">
            <table cellpadding="0" cellspacing="0">
              <tr>
                <td style="padding-right:12px;vertical-align:middle;">
                  <div style="width:40px;height:40px;background:#6c63ff;border-radius:10px;
                    text-align:center;line-height:40px;font-size:20px;">✓</div>
                </td>
                <td style="vertical-align:middle;">
                  <span style="font-size:18px;font-weight:700;color:#ffffff;">FactChecker</span>
                  <span style="font-size:18px;font-weight:700;color:#f59e0b;"> AI</span>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Divider -->
        <tr><td style="height:1px;background:#2a3147;margin:0 32px;"></td></tr>

        <!-- Body -->
        <tr>
          <td style="padding:28px 32px;">

            <p style="margin:0 0 8px;font-size:22px;font-weight:700;color:#ffffff;">
              Password Reset
            </p>
            <p style="margin:0 0 24px;font-size:14px;color:#8892a4;line-height:1.6;">
              We received a request to reset your password. Use the code below — it's valid for
              <strong style="color:#ffffff;">10 minutes</strong>.
            </p>

            <!-- OTP digits -->
            <table cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
              <tr>{digits}</tr>
            </table>

            <!-- Security tip -->
            <table width="100%" cellpadding="0" cellspacing="0"
              style="background:#1c2333;border-radius:12px;padding:14px 16px;margin-bottom:24px;">
              <tr>
                <td>
                  <p style="margin:0;font-size:13px;color:#8892a4;line-height:1.6;">
                    🔒 <strong style="color:#c9d1d9;">Security tip:</strong> Never share this code with
                    anyone. FactChecker AI will never ask for it via chat or phone.
                  </p>
                </td>
              </tr>
            </table>

            <p style="margin:0;font-size:13px;color:#6b7280;line-height:1.6;">
              If you didn't request a password reset, you can safely ignore this email.
              Your account remains secure.
            </p>

          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:16px 32px 24px;border-top:1px solid #2a3147;">
            <p style="margin:0;font-size:12px;color:#4b5563;text-align:center;">
              Sent by FactChecker AI · {FROM_EMAIL}
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    resp = requests.post(
        BREVO_API_URL,
        headers={
            "api-key": BREVO_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "sender":      {"name": FROM_NAME, "email": FROM_EMAIL},
            "to":          [{"email": to_email}],
            "subject":     f"Your verification code is {otp}",
            "htmlContent": html,
        },
        timeout=15,
    )

    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Brevo API error {resp.status_code}: {resp.text}")

    logger.info("OTP email sent via Brevo to %s", to_email)
    return True
