"""WhatsApp digest via CallMeBot (unofficial free service). Skipped silently when not configured.

Privacy: CallMeBot is a third party, so this channel carries the PUBLIC market digest only -
never portfolio data.
"""
import os

import requests

LIMIT = 1000  # keep messages short; CallMeBot passes the text in a URL
MOOD = {"risk-on": "נטייה לסיכון", "risk-off": "בריחה מסיכון", "mixed": "מעורב"}


def daily_text(a: dict, date: str, site_url: str) -> str:
    lines = [f"*דוח שוק יומי – {date}*", f"מצב שוק: {MOOD.get(a.get('market_mood'), 'מעורב')}"]
    ms = a.get("market_state")
    lines.append(ms["headline"] if ms and ms.get("headline") else (a.get("summary") or ""))
    for e in a.get("events", [])[:3]:
        w = ", ".join(s.get("ticker", "") for s in e.get("winners", [])[:3] if s.get("ticker"))
        lines.append(f"\n*{e.get('title')}* ({e.get('severity')}/5)" + (f"\n📈 {w}" if w else ""))
    if site_url:
        lines.append(f"\n{site_url}")
    return "\n".join(lines)[:LIMIT]


def weekly_text(a: dict, rng: str, site_url: str) -> str:
    lines = [f"*סיכום שבועי – {rng}*", a.get("summary") or ""]
    for t in a.get("themes", [])[:3]:
        lines.append(f"\n*{t.get('title')}* ({t.get('trend')})")
    if site_url:
        lines.append(f"\n{site_url}weekly.html")
    return "\n".join(lines)[:LIMIT]


def send(text: str) -> bool:
    phone, key = os.environ.get("WHATSAPP_PHONE"), os.environ.get("CALLMEBOT_APIKEY")
    if not (phone and key):
        print("[whatsapp] not configured; skipping")
        return False
    r = requests.get("https://api.callmebot.com/whatsapp.php", timeout=60,
                     params={"phone": phone, "text": text, "apikey": key})
    if not r.ok:  # never print the URL: it contains the phone number and key
        raise RuntimeError(f"CallMeBot {r.status_code}")
    print("[whatsapp] sent")
    return True
