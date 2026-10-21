import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

def _load_env_fallback():
    # Tente de charger via dotenv si dispo, sinon parse direct le fichier .env
    for candidate in [Path("/app/.env"), Path(".env"), Path("/mnt/disks/data/search_app/.env")]:
        if candidate.exists():
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k not in os.environ or not os.environ[k]:
                        os.environ[k] = v

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

def _get_email_template(code: str, title: str, subtitle: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0b0f19; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #e2e8f0;">
    <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #0b0f19; padding: 40px 10px;">
        <tr>
            <td align="center">
                <table width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 480px; background-color: #111827; border: 1px solid #1f293d; border-radius: 20px; overflow: hidden; box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);">
                    <!-- Barre dégradée néon -->
                    <tr>
                        <td style="height: 4px; background: linear-gradient(90deg, #2563eb, #6366f1, #9333ea);"></td>
                    </tr>
                    
                    <!-- Header -->
                    <tr>
                        <td style="padding: 32px 32px 16px 32px; text-align: center;">
                            <div style="display: inline-block; padding: 10px 16px; background-color: rgba(99, 102, 241, 0.1); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 9999px; margin-bottom: 16px;">
                                <span style="font-size: 11px; font-weight: 700; color: #818cf8; letter-spacing: 1px; text-transform: uppercase;">BRIXHUB OSINT</span>
                            </div>
                            <h1 style="margin: 0; font-size: 20px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px;">{title}</h1>
                            <p style="margin: 8px 0 0 0; font-size: 13px; color: #94a3b8; line-height: 1.5;">{subtitle}</p>
                        </td>
                    </tr>

                    <!-- Code OTP Box -->
                    <tr>
                        <td style="padding: 16px 32px 24px 32px;" align="center">
                            <div style="background-color: #0b0f19; border: 1px solid #243048; border-radius: 14px; padding: 18px 24px; text-align: center; max-width: 260px;">
                                <span style="font-size: 32px; font-weight: 800; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; letter-spacing: 8px; color: #60a5fa;">{code}</span>
                            </div>
                            <p style="margin: 12px 0 0 0; font-size: 11px; color: #64748b;">Ce code à usage unique expire dans <strong style="color: #cbd5e1;">10 minutes</strong>.</p>
                        </td>
                    </tr>

                    <!-- Séparateur -->
                    <tr>
                        <td style="padding: 0 32px;">
                            <div style="height: 1px; background-color: #1f293d;"></div>
                        </td>
                    </tr>

                    <!-- Footer Note -->
                    <tr>
                        <td style="padding: 24px 32px; text-align: center;">
                            <p style="margin: 0 0 8px 0; font-size: 11px; color: #475569; line-height: 1.5;">
                                Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet email en toute sécurité.
                            </p>
                            <p style="margin: 0; font-size: 10px; color: #334155; font-family: ui-monospace, monospace;">
                                &copy; 2026 BrixHub Investigation Engine &bull; Protection des données
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

def send_otp_email_sync(*args, **kwargs):
    _load_env_fallback()
    return _send_otp_email_sync(*args, **kwargs)

def _send_otp_email_sync(to_email: str, code: str, title: str, subtitle: str) -> None:
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    from_name = os.getenv("SMTP_FROM_NAME", "BrixHub Security")
    from_email = os.getenv("SMTP_FROM_EMAIL", smtp_user)

    if not smtp_user or not smtp_pass:
        print(f"[SMTP WARNING] Identifiants SMTP non configurés. Code {code} affiché en console seulement.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{code} est votre code de vérification BrixHub"
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email

    text_content = f"{title}\n\nVotre code de vérification est : {code}\nCe code expire dans 10 minutes.\n\nBrixHub OSINT"
    html_content = _get_email_template(code, title, subtitle)

    msg.attach(MIMEText(text_content, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_email, [to_email], msg.as_string())
        print(f"[SMTP SUCCESS] Email envoyé avec succès à {to_email} !")
    except Exception as e:
        print(f"[SMTP ERROR] Échec lors de l'envoi à {to_email} : {e}")
