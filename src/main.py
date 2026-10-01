"""Daily pipeline: collect -> analyze -> market snapshot -> render -> email.

Usage:
  python src/main.py              full run (needs ANTHROPIC_API_KEY, RESEND_API_KEY, REPORT_TO_EMAIL)
  python src/main.py --no-email   build site only
  python src/main.py --demo       offline sample data, no API keys, no email
"""
import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from market import snapshot, tickers_from  # noqa: E402
from render import ROOT, render  # noqa: E402

DEMO = {
    "summary": "נתוני הדגמה: מתיחות במזרח התיכון ומחסור בשבבי זיכרון מזיזים את השוק לכיוון ביטחוניות ושבבים.",
    "market_mood": "mixed",
    "events": [
        {"title": "ניסיון חטיפת מטוס אייר דובאי", "category": "תעופה", "severity": 3,
         "what_happened": "ניסיון חטיפה סוכל בטיסה מדובאי. הנוסעים והצוות לא נפגעו.",
         "regions": ["המפרץ", "ישראל"], "impact": "חברות תעופה זרות תחת לחץ; אל על נהנית מתשומת לב ומביקוש לשירותי ביטחון.",
         "winners": [{"ticker": "ELAL.TA", "name": "אל על", "reason": "ביקוש לטיסות ישירות ותנופת מומנטום", "confidence": "בינונית"}],
         "losers": [{"ticker": "DAL", "name": "Delta", "reason": "חשיפה לעלויות ביטחון וביקוש חלש"}],
         "sources": [{"title": "הדגמה", "url": "https://example.com"}]},
        {"title": "משבר שבבי זיכרון ואחסון", "category": "שבבים וטכנולוגיה", "severity": 4,
         "what_happened": "מחסור גובר ב-DRAM וב-NAND מעלה מחירים בעקבות ביקוש ל-AI.",
         "regions": ["טייוואן", "דרום קוריאה", "ארה\"ב"], "impact": "יצרניות זיכרון ואחסון נהנות ממחירים גבוהים; יצרניות מחשבים ורכב נפגעות.",
         "winners": [{"ticker": "MU", "name": "Micron", "reason": "עליית מחירי DRAM", "confidence": "גבוהה"},
                     {"ticker": "WDC", "name": "Western Digital", "reason": "ביקוש לאחסון", "confidence": "בינונית"},
                     {"ticker": "NVDA", "name": "Nvidia", "reason": "ביקוש מתמשך לשבבי AI", "confidence": "בינונית"}],
         "losers": [{"ticker": "HPQ", "name": "HP", "reason": "עלויות רכיבים גבוהות"}],
         "sources": [{"title": "הדגמה", "url": "https://example.com"}]},
        {"title": "הסלמה ביטחונית בישראל ובאוקראינה", "category": "גיאופוליטי", "severity": 5,
         "what_happened": "המשך לחימה בשתי זירות מגביר הוצאות ביטחוניות.",
         "regions": ["ישראל", "אוקראינה", "אירופה"], "impact": "ביקוש לנשק, מודיעין ו-AI ביטחוני; נפט וזהב עולים.",
         "winners": [{"ticker": "PLTR", "name": "Palantir", "reason": "חוזי ביטחון ו-AI", "confidence": "גבוהה"},
                     {"ticker": "ESLT.TA", "name": "אלביט", "reason": "צבר הזמנות גדל", "confidence": "גבוהה"},
                     {"ticker": "LMT", "name": "Lockheed Martin", "reason": "תקציבי הגנה", "confidence": "בינונית"}],
         "losers": [{"ticker": "RYAAY", "name": "Ryanair", "reason": "מחירי דלק ובהלה בטיסות"}],
         "sources": [{"title": "הדגמה", "url": "https://example.com"}]},
    ],
    "regions_to_watch": [
        {"region": "ארה\"ב", "stance": "להעדיף", "why": "חשיפה לשבבים, ביטחון ו-AI."},
        {"region": "ישראל", "stance": "להעדיף", "why": "ביטחוניות וסייבר נהנות מהמצב."},
        {"region": "אירופה", "stance": "להיזהר", "why": "תלות באנרגיה וחשיפה לאוקראינה."},
    ],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-email", action="store_true")
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()
    date = datetime.now().strftime("%Y-%m-%d")

    if args.demo:
        analysis = DEMO
    else:
        from analyze import analyze
        from collect import collect
        headlines = collect()
        print(f"[main] {len(headlines)} headlines")
        analysis = analyze(headlines) if headlines else {"summary": "לא נאספו כותרות היום.", "events": [], "regions_to_watch": []}

    market = snapshot(tickers_from(analysis))
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    with open(os.path.join(ROOT, "data", f"{date}.json"), "w", encoding="utf-8") as f:
        json.dump({"analysis": analysis, "market": market}, f, ensure_ascii=False, indent=2)

    out = render(analysis, market, date)
    if args.demo:
        with open(os.path.join(ROOT, "email_preview.html"), "w", encoding="utf-8") as f:
            f.write(out["email_html"])
    if not (args.no_email or args.demo):
        from send_email import send
        top = max((e.get("severity", 0) for e in analysis.get("events", [])), default=0)
        send(f"דוח שוק יומי {date} | חומרה מקסימלית {top}/5", out["email_html"])


if __name__ == "__main__":
    main()
