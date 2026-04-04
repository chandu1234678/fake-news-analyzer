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
FROM_EMAIL    = os.getenv("SMTP_USER", "factcheckai2@gmail.com")
FROM_NAME     = "FactChecker AI"

logger = logging.getLogger(__name__)


def generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def send_otp_email(to_email: str, otp: str) -> bool:
    if not BREVO_API_KEY:
        raise RuntimeError("BREVO_API_KEY is not configured.")

    digit_cells = "".join([
        f"""<td style="padding:0 5px;">
<div style="
  width:56px;height:72px;
  background:#f5f5f7;
  border-radius:14px;
  font-size:36px;font-weight:600;
  color:#1d1d1f;
  text-align:center;line-height:72px;
  font-family:-apple-system,'SF Pro Display','Helvetica Neue',Helvetica,Arial,sans-serif;
  letter-spacing:-1px;
">{d}</div></td>"""
        for d in otp
    ])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Your verification code</title>
</head>
<body style="margin:0;padding:0;background:#ffffff;font-family:-apple-system,'SF Pro Text','Helvetica Neue',Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;color:#1d1d1f;">

  <table width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;padding:64px 24px 48px;">
    <tr><td align="center">
      <table width="480" cellpadding="0" cellspacing="0" style="max-width:480px;width:100%;">

        <!-- Logo mark -->
        <tr>
          <td align="center" style="padding-bottom:40px;">
            <div style="
              width:56px;height:56px;
              background:#1d1d1f;
              border-radius:14px;
              text-align:center;line-height:56px;
              font-size:26px;
            ">✓</div>
          </td>
        </tr>

        <!-- Headline -->
        <tr>
          <td align="center" style="padding-bottom:12px;">
            <h1 style="margin:0;font-size:28px;font-weight:700;color:#1d1d1f;letter-spacing:-0.5px;line-height:1.2;">
              Verify it's you
            </h1>
          </td>
        </tr>

        <!-- Subtext -->
        <tr>
          <td align="center" style="padding-bottom:48px;">
            <p style="margin:0;font-size:17px;color:#6e6e73;line-height:1.5;max-width:360px;">
              Enter this code to reset your FactChecker AI password.
              It expires in 10 minutes.
            </p>
          </td>
        </tr>

        <!-- OTP digits -->
        <tr>
          <td align="center" style="padding-bottom:48px;">
            <table cellpadding="0" cellspacing="0">
              <tr>{digit_cells}</tr>
            </table>
          </td>
        </tr>

        <!-- Divider -->
        <tr>
          <td style="height:1px;background:#d2d2d7;margin-bottom:32px;"></td>
        </tr>

        <!-- Security note -->
        <tr>
          <td align="center" style="padding-top:32px;padding-bottom:16px;">
            <p style="margin:0;font-size:13px;color:#6e6e73;line-height:1.6;max-width:380px;">
              Never share this code with anyone.
              FactChecker AI will never ask for it by phone or message.
            </p>
          </td>
        </tr>

        <!-- Ignore note -->
        <tr>
          <td align="center" style="padding-bottom:48px;">
            <p style="margin:0;font-size:13px;color:#aeaeb2;line-height:1.6;">
              Didn't request this? Ignore this email — your account is safe.
            </p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td align="center">
            <p style="margin:0;font-size:12px;color:#aeaeb2;letter-spacing:0.1px;">
              FactChecker AI &nbsp;·&nbsp; © 2026
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
