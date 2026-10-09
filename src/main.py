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
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from market import snapshot, tickers_from  # noqa: E402
from render import OUT, ROOT, render, render_weekly  # noqa: E402

DEMO = {
    "summary": "נתוני הדגמה: מתיחות במזרח התיכון ומחסור בשבבי זיכרון מזיזים את השוק לכיוון ביטחוניות ושבבים.",
    "market_mood": "mixed",
    "events": [
        {"title": "ניסיון חטיפת מטוס אייר דובאי", "category": "תעופה", "severity": 3,
         "what_happened": "ניסיון חטיפה סוכל בטיסה מדובאי. הנוסעים והצוות לא נפגעו.",
         "regions": ["המפרץ", "ישראל"], "horizons": {"short": {"outlook": "חיובי", "when": "ימים עד שבועות", "tickers": ["ELAL.TA"], "why": "תשומת לב ומומנטום; עלול להתהפך אם יתברר שהאירוע בודד."},
                      "medium": {"outlook": "ניטרלי", "when": "חודשים", "tickers": [], "why": "התלות בעלויות דלק וביקוש לטיסות."},
                      "long": {"outlook": "ניטרלי", "when": "שנה ומעלה", "tickers": [], "why": "אין שינוי מבני מהאירוע עצמו."}},
         "impact": "חברות תעופה זרות תחת לחץ; אל על נהנית מתשומת לב ומביקוש לשירותי ביטחון.",
         "winners": [{"ticker": "ELAL.TA", "name": "אל על", "reason": "ביקוש לטיסות ישירות ותנופת מומנטום", "confidence": "בינונית"}],
         "losers": [{"ticker": "DAL", "name": "Delta", "reason": "חשיפה לעלויות ביטחון וביקוש חלש"}],
         "sources": [{"title": "הדגמה", "url": "https://example.com"}]},
        {"title": "משבר שבבי זיכרון ואחסון", "category": "שבבים וטכנולוגיה", "severity": 4,
         "what_happened": "מחסור גובר ב-DRAM וב-NAND מעלה מחירים בעקבות ביקוש ל-AI.",
         "regions": ["טייוואן", "דרום קוריאה", "ארה\"ב"], "horizons": {"short": {"outlook": "חיובי", "when": "ימים עד שבועות", "tickers": ["MU"], "why": "מחירי DRAM עולים ומשקפים דיווחים קרובים."},
                      "medium": {"outlook": "חיובי", "when": "חודשים", "tickers": ["MU", "WDC"], "why": "מחסור מבני עד שקיבולת חדשה תעלה."},
                      "long": {"outlook": "שלילי", "when": "שנה ומעלה", "tickers": [], "why": "תוספת קיבולת עלולה להוביל לעודף היצע."}},
         "impact": "יצרניות זיכרון ואחסון נהנות ממחירים גבוהים; יצרניות מחשבים ורכב נפגעות.",
         "winners": [{"ticker": "MU", "name": "Micron", "reason": "עליית מחירי DRAM", "confidence": "גבוהה"},
                     {"ticker": "WDC", "name": "Western Digital", "reason": "ביקוש לאחסון", "confidence": "בינונית"},
                     {"ticker": "NVDA", "name": "Nvidia", "reason": "ביקוש מתמשך לשבבי AI", "confidence": "בינונית"}],
         "losers": [{"ticker": "HPQ", "name": "HP", "reason": "עלויות רכיבים גבוהות"}],
         "sources": [{"title": "הדגמה", "url": "https://example.com"}]},
        {"title": "הסלמה ביטחונית בישראל ובאוקראינה", "category": "גיאופוליטי", "severity": 5,
         "what_happened": "המשך לחימה בשתי זירות מגביר הוצאות ביטחוניות.",
         "regions": ["ישראל", "אוקראינה", "אירופה"], "horizons": {"short": {"outlook": "חיובי", "when": "ימים עד שבועות", "tickers": ["PLTR"], "why": "כותרות מעלות ביקוש."},
                      "medium": {"outlook": "חיובי", "when": "חודשים", "tickers": ["ESLT.TA", "LMT"], "why": "צבר הזמנות והגדלות תקציב."},
                      "long": {"outlook": "חיובי", "when": "שנה ומעלה", "tickers": ["PLTR"], "why": "הוצאות ביטחון מבניות באירופה ובישראל."}},
         "impact": "ביקוש לנשק, מודיעין ו-AI ביטחוני; נפט וזהב עולים.",
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

DEMO_WEEKLY = {
    "summary": "הדגמה: שבוע של מתיחות ביטחונית ומחסור בזיכרון. ביטחוניות ושבבים הובילו.",
    "market_mood": "mixed",
    "themes": [{"title": "מחסור בשבבי זיכרון", "trend": "מתעצם", "what_happened": "מחירי DRAM עלו כל השבוע.",
                "market_impact": "יצרניות זיכרון מרוויחות.", "tickers": [{"ticker": "MU", "note": "הרוויחה מהעלייה במחירים"}]}],
    "best_ideas": [{"ticker": "PLTR", "name": "Palantir", "horizon": "ארוך", "why": "ביקוש ביטחוני מבני."}],
    "risks": ["היפוך חד בנפט", "חדשות על הפסקת אש"],
    "watch_next_week": ["דוחות רבעוניים של יצרניות שבבים"],
    "regions_to_watch": [{"region": "ישראל", "stance": "להעדיף", "why": "ביטחוניות וסייבר."}],
    "outlook": {"short": "תנודתיות גבוהה", "medium": "נטייה חיובית לשבבים וביטחוניות", "long": "תקציבי ביטחון ו-AI ימשיכו לגדול"},
}

DEMO["market_state"] = {
    "headline": "הדגמה: שוק מעורב עם נטייה זהירה",
    "context": "אירועי היום מעלים ביקוש לביטחוניות ולשבבים, בעוד תשואות האג\"ח גבוהות.",
    "analysis": "מדדי המניות מתחת לשיאים, VIX מעט גבוה, הזהב מחזיק. המומנטום בשבבים חזק יחסית.",
    "recommendation": "סטנס ניטרלי-זהיר: להעדיף שבבים וביטחוניות, להימנע מחשיפה מוגברת לתעופה.",
    "by_horizon": {"short": "תנודתיות גבוהה", "medium": "נטייה חיובית לשבבים", "long": "תקציבי ביטחון ו-AI ממשיכים לגדול"},
    "levels_to_watch": ["S&P 500 – 50 יום", "תשואת 10Y"], "risks": ["הפסקת אש פתאומית", "עליית תשואות"],
}
DEMO["indices"] = [{"symbol": "^GSPC", "name": "S&P 500", "price": 5800.0, "d1": 0.4, "w1": -0.8, "m1": 2.1, "from_52w_high": -3.2}]
DEMO_PORTFOLIO = [
    {"ticker": "NVDA", "name": "NVIDIA", "type": "stock", "qty": 100, "cost": 100.0, "currency": "USD"},
    {"ticker": "5134135", "name": "קרן מדד (ללא נתוני שוק)", "type": "fund", "qty": 1000, "cost": 10.0, "currency": "ILS"},
]
DEMO["candidates"] = {"theme": "הדגמה: מתיחות באנרגיה וביקוש לשבבים.", "picks": {
    "אנרגיה": [{"ticker": "XLE", "name": "Energy Select Sector SPDR", "type": "etf", "price": 90.0, "d1": 0.8, "w1": 2.1, "m1": 4.0, "from_52w_high": -6.0,
                "thesis": "שיבושי אספקה ומתיחות בהורמוז תומכים במחירי הנפט.", "horizon": "בינוני", "conviction": "בינונית", "risk": "הפסקת אש חדה תוריד את מחירי הנפט.",
                "buy_below": 88.0, "target": 100.0, "stop": 82.0}],
    "שבבים, זיכרון ותשתית": [{"ticker": "SMH", "name": "VanEck Semiconductor ETF", "type": "etf", "price": 300.0, "d1": 0.5, "w1": 1.0, "m1": 3.0, "from_52w_high": -4.0,
                "thesis": "מחסור בזיכרון מקדם ביקוש לתעשייה כולה.", "horizon": "בינוני", "conviction": "בינונית", "risk": "תנודתיות גבוהה וריכוז ב-NVDA.",
                "buy_below": 290.0, "target": 340.0, "stop": 270.0}]}}
DEMO_GOAL = {"target_ils": 65000, "deadline": "2026-12-31", "start_ils": 41600, "start_date": "2026-10-07"}
DEMO_PA = {
    "summary": "הדגמה: תיק מרוכז בשבבים. הקרן מוחזקת ללא נתוני שוק.", "health": "בינוני",
    "top_actions": [{"ticker": "NVDA", "horizon": "medium", "text": "להקטין חשיפה כדי להפחית ריכוזיות"}, {"ticker": "5134135", "horizon": "short", "text": "להמשיך להחזיק את הקרן"}],
    "exposure_to_today": "משבר הזיכרון תומך בחלק גדול מהתיק.", "concentration": "ריכוז גבוה בסקטור השבבים ובדולר.",
    "risks": ["תיקון בסקטור השבבים"],
    "positions": [
        {"ticker": "NVDA", "analysis": "מומנטום חזק, אך משקל גבוה בתיק.", "buy_below": 210, "sell_above": 270, "stop": 200, "levels_note": "הדגמה", "watch": "שבירת ממוצע 50 יום",
         "short": {"action": "להחזיק", "size_pct": 0, "why": "מומנטום חיובי"}, "medium": {"action": "להקטין", "size_pct": 20, "why": "ריכוזיות"}, "long": {"action": "להחזיק", "why": "מגמת AI"}},
        {"ticker": "5134135", "analysis": "קרן ללא נתוני שוק; ניתוח איכותי בלבד.", "watch": "",
         "short": {"action": "להחזיק", "why": "אין נתונים"}, "medium": {"action": "לעקוב", "why": "תלוי בסחורות"}, "long": {"action": "להחזיק", "why": "פיזור"}},
    ],
}


def _telegram(build):
    """Telegram is a bonus channel: a failure here must never fail the report."""
    try:
        import telegram_digest as t
        t.send(build(t))
    except Exception as exc:
        print(f"[telegram] failed: {exc}")


def _whatsapp(build):
    """WhatsApp (CallMeBot) is a bonus channel carrying public content only; failures are non-fatal."""
    try:
        import whatsapp as w
        w.send(build(w))
    except Exception as exc:
        print(f"[whatsapp] failed: {type(exc).__name__}: {exc}")


def _portfolio(args, analysis, ms=None):
    """Private portfolio analysis -> (pf, pa) for email/Telegram only. Never persisted; failures are non-fatal."""
    import portfolio
    try:
        holdings = DEMO_PORTFOLIO if args.demo else portfolio.load()
        if not holdings:
            return None, None
        pf = portfolio.build(holdings)
        goal = portfolio.goal_status(pf, DEMO_GOAL if args.demo else portfolio.load_goal()) if (args.demo or portfolio.load_goal()) else None
        if args.demo:
            pa = json.loads(json.dumps(DEMO_PA))
        else:
            from analyze import analyze_portfolio
            pa = analyze_portfolio(portfolio.for_ai(pf), analysis, ms, goal)
        pa["goal"] = goal
        portfolio.annotate(pf, pa)  # percentages -> concrete amounts, computed locally
        return pf, pa
    except Exception as exc:  # message omitted on purpose: never risk echoing private data to logs
        print(f"[portfolio] failed: {type(exc).__name__}")
        return None, None


def run_weekly(args, date):
    import glob
    files = sorted(glob.glob(os.path.join(ROOT, "data", "????-??-??.json")))[-7:]
    days = [{"date": os.path.basename(f)[:-5], **json.load(open(f, encoding="utf-8"))} for f in files]
    if args.demo:
        analysis = DEMO_WEEKLY
    elif not days:
        print("[weekly] no daily data yet; skipping")
        return
    else:
        from analyze import analyze_weekly
        analysis = analyze_weekly(days)
    tickers = list(dict.fromkeys(
        [i["ticker"] for i in analysis.get("best_ideas", [])] +
        [s["ticker"] for t in analysis.get("themes", []) for s in t.get("tickers", [])]))
    market = snapshot(tickers) if tickers else {}
    start = days[0]["date"] if days else date
    pf, pa = _portfolio(args, {"summary": analysis.get("summary", ""), "events": []})
    out = render_weekly(analysis, market, date, start, pf, pa)
    if args.demo:
        with open(os.path.join(OUT(), "weekly_email_preview.html"), "w", encoding="utf-8") as f:
            f.write(out["email_html"])
    elif not args.no_email:
        from send_email import send
        send(f"סיכום שבועי {date}", out["email_html"])
        _telegram(lambda t: t.weekly_text(analysis, f"{start} – {date}", os.environ.get("SITE_URL", ""), pf, pa))
        _whatsapp(lambda w: w.weekly_text(analysis, f"{start} – {date}", os.environ.get("SITE_URL", "")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-email", action="store_true")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--weekly", action="store_true", help="weekly summary only")
    args = ap.parse_args()
    date = datetime.now().strftime("%Y-%m-%d")
    if args.demo:
        os.environ["DEMO_OUT"] = os.path.join(ROOT, "demo_out")
    if args.weekly:
        run_weekly(args, date)
        return
    # scheduled retry runs are no-ops once today's report exists (manual runs always execute)
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and os.path.exists(os.path.join(ROOT, "data", f"{date}.json")):
        print("[main] today's report already exists; skipping")
        return

    if args.demo:
        analysis = DEMO
    else:
        from analyze import analyze
        from collect import collect
        headlines = collect()
        print(f"[main] {len(headlines)} headlines")
        analysis = analyze(headlines) if headlines else {"summary": "לא נאספו כותרות היום.", "events": [], "regions_to_watch": []}

    market = snapshot(tickers_from(analysis))
    if not args.demo:
        try:  # market-state section: macro dashboard + AI context/analysis/recommendation (public-safe)
            from analyze import analyze_market_state
            from market import indices
            analysis["indices"] = indices()
            if analysis["indices"]:
                analysis["market_state"] = analyze_market_state(analysis["indices"], analysis)
        except Exception as exc:
            print(f"[market_state] failed: {type(exc).__name__}: {exc}")
    if not args.demo:
        try:  # investment candidates by category (public market data + world picture; no portfolio data)
            import candidates
            from analyze import analyze_candidates
            data = candidates.gather()
            analysis["candidates"] = candidates.validate(analyze_candidates(data, analysis, analysis.get("market_state")), data)
        except Exception as exc:
            print(f"[candidates] failed: {type(exc).__name__}: {exc}")
    os.makedirs(os.path.join(OUT(), "data"), exist_ok=True)
    with open(os.path.join(OUT(), "data", f"{date}.json"), "w", encoding="utf-8") as f:
        json.dump({"analysis": analysis, "market": market}, f, ensure_ascii=False, indent=2)

    pf, pa = _portfolio(args, analysis, analysis.get("market_state"))  # after data/ is saved: portfolio never lands there
    import candidates as _c
    cand_extra = _c.personalize(analysis.get("candidates"), pf)  # private: exposure + affordable units -> email only
    out = render(analysis, market, date, pf, pa, cand_extra)
    if args.demo:
        with open(os.path.join(OUT(), "email_preview.html"), "w", encoding="utf-8") as f:
            f.write(out["email_html"])
    if not (args.no_email or args.demo):
        from send_email import send
        top = max((e.get("severity", 0) for e in analysis.get("events", [])), default=0)
        send(f"דוח שוק יומי {date} | חומרה מקסימלית {top}/5", out["email_html"])
        _telegram(lambda t: t.daily_text(analysis, date, os.environ.get("SITE_URL", ""), pf, pa))
        _whatsapp(lambda w: w.daily_text(analysis, date, os.environ.get("SITE_URL", "")))
    if datetime.now().weekday() == 4 and not args.demo:  # Friday
        try:
            run_weekly(args, date)
        except Exception as exc:  # weekly failure must not fail the daily run
            print(f"[weekly] failed: {exc}")


if __name__ == "__main__":
    main()
