"""Send HTML emails with file attachments via Gmail SMTP + App Password."""
from __future__ import annotations

import base64
import mimetypes
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

LOGO_PATH = Path(__file__).parent.parent / "staffinc_logo.png"

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f8;">
<tr><td align="center" style="padding:36px 16px;">

  <table width="600" cellpadding="0" cellspacing="0"
         style="background:#ffffff;border-radius:10px;overflow:hidden;
                box-shadow:0 4px 16px rgba(0,0,0,0.10);">

    <!-- HEADER -->
    <tr>
      <td style="background:linear-gradient(135deg,#f5c800 0%,#f7d940 100%);
                 padding:32px 40px 28px;">
        {logo_block}
        <p style="margin:6px 0 0;color:#7a6000;font-size:12px;
                  letter-spacing:2px;text-transform:uppercase;">
          Finance &amp; Treasury
        </p>
      </td>
    </tr>

    <!-- DIVIDER BAR -->
    <tr><td style="height:4px;background:#ffffff;"></td></tr>

    <!-- BODY -->
    <tr>
      <td style="padding:36px 40px 28px;">
        <p style="margin:0 0 20px;font-size:15px;color:#1a1a1a;">Dear {financier},</p>
        <p style="margin:0 0 20px;font-size:15px;color:#1a1a1a;line-height:1.6;">
          Please find attached the latest bank statements for:
        </p>

        <!-- ENTITY HIGHLIGHT BOX -->
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
          <tr>
            <td style="background:#fffbea;border-left:4px solid #f5c800;
                       border-radius:0 6px 6px 0;padding:14px 20px;">
              <span style="font-size:15px;font-weight:700;color:#1a1a1a;">
                {entity_list}
              </span><br>
              <span style="font-size:13px;color:#7a6000;margin-top:4px;display:block;">
                Reporting period: <strong>{period}</strong>
              </span>
            </td>
          </tr>
        </table>

        {part_note_block}

        <p style="margin:0 0 20px;font-size:15px;color:#1a1a1a;line-height:1.6;">
          Kindly acknowledge receipt of this statement at your earliest convenience.
          Should you have any questions, please do not hesitate to reach out.
        </p>

        <p style="margin:0;font-size:15px;color:#1a1a1a;line-height:1.8;">
          Kind regards,<br>
          <strong style="color:#1a1a1a;">{from_name}</strong><br>
          <span style="font-size:13px;color:#5a7a9a;">Finance &amp; Treasury</span>
        </p>
      </td>
    </tr>

    <!-- FOOTER -->
    <tr>
      <td style="background:#f7f9fc;border-top:1px solid #e2e8f0;
                 padding:18px 40px;">
        <p style="margin:0;font-size:11px;color:#8fa3b8;line-height:1.6;">
          This is an automated message from {from_name}. The attached files are
          confidential and intended solely for the named recipient. If you have
          received this in error, please notify the sender and delete it immediately.
        </p>
      </td>
    </tr>

  </table>
</td></tr>
</table>
</body>
</html>
"""


def _logo_block() -> str:
    if LOGO_PATH.exists():
        data = base64.b64encode(LOGO_PATH.read_bytes()).decode()
        ext = LOGO_PATH.suffix.lstrip(".")
        return (
            f'<img src="data:image/{ext};base64,{data}" '
            f'alt="StaffInc" height="48" style="display:block;margin-bottom:8px;">'
        )
    return (
        '<h1 style="margin:0;color:#1a1a1a;font-size:28px;font-weight:800;'
        'letter-spacing:1px;">StaffInc</h1>'
    )


def _part_note_block(part_note: str) -> str:
    if not part_note.strip():
        return ""
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;">'
        f'<tr><td style="background:#fff8e6;border-left:4px solid #f0a500;'
        f'border-radius:0 6px 6px 0;padding:12px 20px;">'
        f'<span style="font-size:13px;color:#7a5700;">{part_note.strip()}</span>'
        f'</td></tr></table>'
    )


class GmailSender:
    def __init__(self, from_name: str = "", from_address: str = ""):
        self.address = from_address or os.environ["GMAIL_ADDRESS"]
        self.password = os.environ["GMAIL_APP_PASSWORD"]
        self.from_name = from_name
        self.from_header = f"{from_name} <{self.address}>" if from_name else self.address

    def send(self, to: str, subject: str, body: str, attachments: list[str],
             financier: str = "", entity_list: str = "",
             period: str = "", part_note: str = "") -> str:
        msg = EmailMessage()
        msg["To"] = to
        msg["From"] = self.from_header
        msg["Subject"] = subject
        msg.set_content(body)

        html = _HTML_TEMPLATE.format(
            logo_block=_logo_block(),
            financier=financier or to,
            entity_list=entity_list,
            period=period,
            from_name=self.from_name,
            part_note_block=_part_note_block(part_note),
        )
        msg.add_alternative(html, subtype="html")

        for path in attachments:
            p = Path(path)
            ctype, _ = mimetypes.guess_type(p.name)
            maintype, subtype = (ctype.split("/", 1) if ctype else ("application", "octet-stream"))
            msg.add_attachment(
                p.read_bytes(), maintype=maintype, subtype=subtype, filename=p.name
            )

        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(self.address, self.password)
            smtp.send_message(msg)

        return f"smtp-{to}-{subject[:20]}"
