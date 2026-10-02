"""Short Telegram digest (daily + weekly). Skipped silently when not configured."""
import html
import os

import requests

LIMIT = 4000  # Telegram max is 4096 characters
MOOD = {"risk-on": "נטייה לסיכון", "risk-off": "בריחה מסיכון", "mixed": "מעורב"}


def _e(x) -> str:
    return html.escape(str(x or ""))


def _pf_lines(pf, pa) -> list:
    if not (pf and pa):
        return []
    t = pf["totals"]
    out = ["", "<b>💼 התיק שלי</b>", f"שינוי יומי משוער: {t['day_pct']:+.2f}%" + (f" · רו\"ה כולל: {t['pnl_pct']:+.1f}%" if t.get("pnl_pct") is not None else "") + f" · מצב: {_e(pa.get('health'))}"]
    out += [f"• {_e(x)}" for x in pa.get("top_actions", [])[:3]]
    return out


def daily_text(a: dict, date: str, site_url: str, pf=None, pa=None) -> str:
    lines = [f"<b>🌍 דוח שוק יומי – {_e(date)}</b>", f"<i>מצב שוק: {MOOD.get(a.get('market_mood'), 'מעורב')}</i>", "", _e(a.get("summary"))]
    ms = a.get("market_state")
    if ms:
        lines += ["", f"<b>📊 {_e(ms.get('headline'))}</b>", _e(ms.get("recommendation"))]
    lines += _pf_lines(pf, pa)
    for e in a.get("events", [])[:5]:
        w = ", ".join(s.get("ticker", "") for s in e.get("winners", [])[:4] if s.get("ticker"))
        l = ", ".join(s.get("ticker", "") for s in e.get("losers", [])[:3] if s.get("ticker"))
        lines += ["", f"<b>{_e(e.get('title'))}</b> (חומרה {_e(e.get('severity'))}/5)"]
        if w:
            lines.append(f"📈 {_e(w)}")
        if l:
            lines.append(f"📉 {_e(l)}")
        h = e.get("horizons") or {}
        parts = [f"{lbl}: {_e(h[k].get('outlook'))}" for k, lbl in (("short", "קצר"), ("medium", "בינוני"), ("long", "ארוך")) if h.get(k)]
        if parts:
            lines.append("⏱ " + " · ".join(parts))
    if site_url:
        lines += ["", f'<a href="{_e(site_url)}">לדוח המלא באתר</a>']
    lines += ["", "<i>אינו ייעוץ השקעות</i>"]
    return "\n".join(lines)[:LIMIT]


def weekly_text(a: dict, rng: str, site_url: str, pf=None, pa=None) -> str:
    lines = [f"<b>🗓️ סיכום שבועי – {_e(rng)}</b>", "", _e(a.get("summary"))] + _pf_lines(pf, pa)
    for t in a.get("themes", [])[:4]:
        lines += ["", f"<b>{_e(t.get('title'))}</b> ({_e(t.get('trend'))})", _e(t.get("market_impact"))]
    ideas = a.get("best_ideas", [])[:4]
    if ideas:
        lines += ["", "<b>רעיונות מובילים</b>"] + [f"• {_e(i.get('ticker'))} ({_e(i.get('horizon'))}) – {_e(i.get('why'))}" for i in ideas]
    if site_url:
        lines += ["", f'<a href="{_e(site_url)}weekly.html">לסיכום המלא</a>']
    lines += ["", "<i>אינו ייעוץ השקעות</i>"]
    return "\n".join(lines)[:LIMIT]


def send(text: str) -> bool:
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        print("[telegram] not configured; skipping")
        return False
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=30,
                      json={"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True})
    if not r.ok:  # never print the URL (it contains the token)
        raise RuntimeError(f"Telegram {r.status_code}: {r.text[:200]}")
    print("[telegram] sent")
    return True
