import os
import random
import string
import requests
from dotenv import load_dotenv

_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(_env_path)

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM    = os.getenv("RESEND_FROM", "FactChecker AI <onboarding@resend.dev>")
RESEND_API_URL = "https://api.resend.com/emails"


def generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def send_otp_email(to_email: str, otp: str) -> bool:
    if not RESEND_API_KEY or RESEND_API_KEY.startswith("your-"):
        raise RuntimeError("RESEND_API_KEY is not configured.")

    digits = "".join([
        f'<td style="padding:0 4px;">'
        f'<div style="width:48px;height:60px;background:#0d1117;border:2px solid #30363d;'
        f'border-radius:10px;font-size:30px;font-weight:700;color:#c0c1ff;'
        f'text-align:center;line-height:60px;font-family:monospace;">{d}</div></td>'
        for d in otp
    ])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Reset your password</title>
</head>
<body style="margin:0;padding:0;background:#090c10;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:#090c10;padding:40px 16px;">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" role="presentation"
  style="max-width:560px;width:100%;background:#0d1117;border-radius:16px;
         border:1px solid #21262d;overflow:hidden;">

  <!-- top accent -->
  <tr>
    <td style="height:3px;background:linear-gradient(90deg,#818cf8,#c0c1ff 40%,#f59e0b 70%,#6ee7b7);"></td>
  </tr>

  <!-- header -->
  <tr>
    <td style="padding:32px 40px 24px;">
      <table cellpadding="0" cellspacing="0" role="presentation">
        <tr>
          <td style="padding-right:10px;vertical-align:middle;">
            <div style="width:36px;height:36px;background:#c0c1ff;border-radius:9px;
              text-align:center;line-height:36px;font-size:18px;font-weight:800;color:#090c10;">✓</div>
          </td>
          <td style="vertical-align:middle;">
            <span style="font-size:20px;font-weight:800;color:#e6edf3;letter-spacing:-0.02em;">FactChecker</span>
            <span style="font-size:20px;font-weight:800;color:#f59e0b;letter-spacing:-0.02em;"> AI</span>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- divider -->
  <tr><td style="height:1px;background:#21262d;margin:0 40px;"></td></tr>

  <!-- body -->
  <tr>
    <td style="padding:32px 40px 28px;">

      <p style="margin:0 0 6px;font-size:24px;font-weight:700;color:#e6edf3;letter-spacing:-0.02em;">
        Reset your password
      </p>
      <p style="margin:0 0 28px;font-size:14px;color:#8b949e;line-height:1.7;">
        We received a password reset request for your account.<br>
        Enter the code below — it expires in <strong style="color:#c0c1ff;">10 minutes</strong>.
      </p>

      <!-- code block -->
      <table width="100%" cellpadding="0" cellspacing="0" role="presentation"
        style="background:#161b22;border:1px solid #30363d;border-radius:12px;
               padding:28px 20px;margin-bottom:28px;">
        <tr>
          <td align="center">
            <p style="margin:0 0 18px;font-size:11px;font-weight:600;color:#6e7681;
              text-transform:uppercase;letter-spacing:0.12em;">Verification Code</p>
            <table cellpadding="0" cellspacing="0" role="presentation">
              <tr>{digits}</tr>
            </table>
            <p style="margin:18px 0 0;font-size:12px;color:#484f58;">
              Valid for 10 minutes &nbsp;·&nbsp; Single use only
            </p>
          </td>
        </tr>
      </table>

      <!-- warning box -->
      <table width="100%" cellpadding="0" cellspacing="0" role="presentation"
        style="background:#161b22;border:1px solid #30363d;border-left:3px solid #f59e0b;
               border-radius:8px;padding:14px 18px;margin-bottom:28px;">
        <tr>
          <td>
            <p style="margin:0;font-size:13px;color:#8b949e;line-height:1.65;">
              <strong style="color:#f59e0b;">Security notice:</strong>
              Never share this code. FactChecker AI will never ask for it by phone or chat.
            </p>
          </td>
        </tr>
      </table>

      <p style="margin:0;font-size:13px;color:#484f58;line-height:1.7;">
        Didn't request this? You can safely ignore this email — your account is unchanged.
      </p>

    </td>
  </tr>

  <!-- footer -->
  <tr>
    <td style="padding:18px 40px 24px;border-top:1px solid #21262d;background:#090c10;">
      <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
        <tr>
          <td>
            <p style="margin:0;font-size:12px;color:#484f58;">
              Sent by <strong style="color:#6e7681;">FactChecker AI</strong>
            </p>
          </td>
          <td align="right">
            <p style="margin:0;font-size:11px;color:#30363d;">© 2026 FactChecker AI</p>
          </td>
        </tr>
      </table>
    </td>
  </tr>

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
            "subject": "Your FactChecker AI reset code",
            "html": html,
        },
        timeout=15,
    )

    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Resend API error {resp.status_code}: {resp.text}")

    return True
