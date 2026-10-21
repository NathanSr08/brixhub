import json
import urllib.request
from app.core.config import get_settings

def notify_search(client_ip: str, criteria: dict) -> None:
    s = get_settings()
    if not s.telegram_chat_id or not s.telegram_bot_token:
        return
    items = [f"• *{k} :* `{v}`" for k, v in criteria.items() if v and k != "limit"]
    if not items:
        return
    lines = ["🔍 *Nouvelle recherche*", f"🌐 *IP :* `{client_ip}`", "📋 *Critères :*"] + items
    payload = {
        "chat_id": s.telegram_chat_id,
        "text": "\n".join(lines),
        "parse_mode": "Markdown"
    }
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"[Telegram Error] {e}")

send_telegram_notification = notify_search
