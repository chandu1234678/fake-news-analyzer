import os
import random
import string
import requests
from dotenv import load_dotenv

_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(_env_path)

RESEND_API_KEY  = os.getenv("RESEND_API_KEY")
# Use your verified Resend domain, or onboarding@resend.dev for testing
RESEND_FROM     = os.getenv("RESEND_FROM", "FactChecker AI <onboarding@resend.dev>")
RESEND_API_URL  = "https://api.resend.com/emails"


def generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def send_otp_email(to_email: str, otp: str) -> bool:
    if not RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY must be set in .env")

    digit_cells = "".join([
        f"""<td style="padding:0 5px;">
              <div style="width:44px;height:56px;background:#1e2228;border:1.5px solid #2a3040;
                border-radius:12px;font-size:28px;font-weight:700;color:#c0c1ff;
                text-align:center;line-height:56px;font-family:'Courier New',monospace;">
                {d}
              </div>
            </td>"""
        for d in otp
    ])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0d1117;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Inter',Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0d1117;padding:48px 16px;">
    <tr><td align="center">
      <table role="presentation" width="520" cellpadding="0" cellspacing="0"
        style="max-width:520px;width:100%;background:#161b22;border-radius:20px;border:1px solid #21262d;overflow:hidden;">

        <!-- Accent bar -->
        <tr><td style="height:4px;background:linear-gradient(90deg,#c0c1ff 0%,#f59e0b 50%,#6ee7b7 100%);"></td></tr>

        <!-- Header -->
        <tr><td style="padding:32px 40px 24px;">
          <table role="presentation" cellpadding="0" cellspacing="0"><tr>
            <td style="padding-right:12px;vertical-align:middle;">
              <div style="width:40px;height:40px;background:#c0c1ff;border-radius:10px;
                text-align:center;line-height:40px;font-size:20px;font-weight:700;color:#0d1117;">✓</div>
            </td>
            <td style="vertical-align:middle;">
              <span style="font-size:22px;font-weight:800;color:#e6edf3;letter-spacing:-0.03em;">FactChecker</span>
              <span style="font-size:22px;font-weight:800;color:#f59e0b;letter-spacing:-0.03em;"> AI</span>
            </td>
          </tr></table>
        </td></tr>

        <tr><td style="height:1px;background:#21262d;"></td></tr>

        <!-- Body -->
        <tr><td style="padding:32px 40px;">
          <p style="margin:0 0 8px;font-size:26px;font-weight:700;color:#e6edf3;letter-spacing:-0.02em;">Password Reset</p>
          <p style="margin:0 0 28px;font-size:14px;color:#8b949e;line-height:1.7;">
            We received a request to reset your FactChecker AI password.<br>
            Use the code below — it expires in <strong style="color:#e6edf3;">10 minutes</strong>.
          </p>

          <!-- OTP digits -->
          <table role="presentation" cellpadding="0" cellspacing="0"
            style="background:#0d1117;border:1px solid #21262d;border-radius:14px;padding:24px 20px;margin:0 0 28px;width:100%;">
            <tr><td align="center">
              <p style="margin:0 0 16px;font-size:11px;font-weight:600;color:#8b949e;text-transform:uppercase;letter-spacing:0.1em;">
                Verification Code
              </p>
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>{digit_cells}</tr>
              </table>
              <p style="margin:16px 0 0;font-size:12px;color:#484f58;">Valid for 10 minutes · Single use only</p>
            </td></tr>
          </table>

          <!-- Security tip -->
          <table role="presentation" cellpadding="0" cellspacing="0"
            style="background:#1c2128;border:1px solid #21262d;border-left:3px solid #f59e0b;
              border-radius:8px;padding:14px 16px;margin:0 0 28px;width:100%;">
            <tr><td>
              <p style="margin:0;font-size:13px;color:#8b949e;line-height:1.6;">
                <strong style="color:#f59e0b;">🔒 Security tip:</strong>
                Never share this code with anyone. FactChecker AI will never ask for it via chat or phone.
              </p>
            </td></tr>
          </table>

          <p style="margin:0;font-size:13px;color:#484f58;line-height:1.7;">
            If you didn't request a password reset, you can safely ignore this email. Your account remains secure.
          </p>
        </td></tr>

        <!-- Footer -->
        <tr><td style="padding:20px 40px 28px;border-top:1px solid #21262d;background:#0d1117;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
            <td><p style="margin:0;font-size:12px;color:#484f58;">
              Sent by <strong style="color:#8b949e;">FactChecker AI</strong>
            </p></td>
            <td align="right"><p style="margin:0;font-size:11px;color:#30363d;">© 2026 FactChecker AI</p></td>
          </tr></table>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    resp = requests.post(
        RESEND_API_URL,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": RESEND_FROM,
            "to": [to_email],
            "subject": "Your FactChecker AI Reset Code",
            "html": html,
        },
        timeout=15,
    )

    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Resend API error {resp.status_code}: {resp.text}")

    return True
