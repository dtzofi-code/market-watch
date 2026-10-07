"""Turn raw headlines into structured market-impact analysis using the Claude API."""
import json
import os
import re
import time

import requests

from config import GEMINI_MODEL, MODEL, REFERENCE_MAP

SYSTEM = f"""אתה אנליסט מאקרו-גיאופוליטי בכיר. תקבל כותרות חדשות מהיממה האחרונה.
משימה: זהה את האירועים והמשברים בעלי השפעה אמיתית על שווקי המניות, קבץ כותרות לאירוע אחד,
והסבר איך כל אירוע משפיע על אזורים, סקטורים ומניות ספציפיות (ארה"ב ותל אביב).

דוגמאות לחשיבה הרצויה:
{REFERENCE_MAP}

כללים:
- התעלם מרעש (ספורט, תרבות, פוליטיקה פנימית ללא השפעה כלכלית).
- אל תמציא עובדות שאינן בכותרות; הסק השפעות רק מתוך הכותרות והידע הכללי שלך.
- בחר 3-8 אירועים, מהחשוב לפחות חשוב. אם אין דבר משמעותי החזר events ריק.
- לכל אירוע חובה להעריך פוטנציאל בשלושה אופקים (קצר/בינוני/ארוך), עם נימוק קונקרטי לכל אחד; באופק הארוך התמקד בשינוי מבני (למשל השקעות בתשתית, שרשראות אספקה, תקציבי ביטחון). אל תתן אותה תחזית לכל האופקים בצורה אוטומטית.
- טיקרים: ארה"ב רגיל (NVDA), תל אביב עם .TA (ESLT.TA). רק טיקרים אמיתיים.
- כתוב בעברית. החזר JSON תקין בלבד, בלי טקסט נוסף, במבנה:
{{
 "summary": "סיכום מנהלים של 2-3 משפטים",
 "market_mood": "risk-on | risk-off | mixed",
 "events": [{{
   "title": "שם האירוע",
   "category": "גיאופוליטי|שבבים וטכנולוגיה|אנרגיה|תעופה|סייבר|בריאות|סחר וסנקציות|אחר",
   "severity": 1-5,
   "what_happened": "2 משפטים",
   "regions": ["אזורים מושפעים"],
   "impact": "איך זה משפיע על השוק",
   "horizons": {{
     "short":  {{"outlook": "חיובי|שלילי|ניטרלי", "when": "ימים עד שבועות", "tickers": ["טיקרים רלוונטיים"], "why": "למה, ומה יכול לשנות את התמונה"}},
     "medium": {{"outlook": "חיובי|שלילי|ניטרלי", "when": "חודשים (עד כשנה)", "tickers": [], "why": ""}},
     "long":   {{"outlook": "חיובי|שלילי|ניטרלי", "when": "שנה ומעלה", "tickers": [], "why": ""}}
   }},
   "winners": [{{"ticker": "", "name": "", "reason": "", "confidence": "גבוהה|בינונית|נמוכה"}}],
   "losers": [{{"ticker": "", "name": "", "reason": ""}}],
   "sources": [{{"title": "", "url": ""}}]
 }}],
 "regions_to_watch": [{{"region": "", "stance": "להעדיף|להיזהר|ניטרלי", "why": ""}}]
}}"""


def _extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def _gemini_candidates(key: str) -> list:
    """GEMINI_MODEL if set, else every text Flash model this key lists (stable names first)."""
    if os.environ.get("GEMINI_MODEL"):
        return [GEMINI_MODEL]
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                     headers={"x-goog-api-key": key}, timeout=30)
    r.raise_for_status()
    names = [m["name"].split("/")[-1] for m in r.json().get("models", [])
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    print("[analyze] available:", ", ".join(names))
    bad = ("image", "tts", "live", "audio", "omni", "robotics", "computer", "embedding", "gemma", "customtools")
    ok = [n for n in names if "flash" in n and not any(x in n for x in bad)]
    # aliases/stable first, then lite; previews last
    ok.sort(key=lambda n: (("preview" in n or "exp" in n), "lite" in n, not n.endswith("-latest")))
    # try one full model first, then the lighter (usually less loaded) ones, then the rest
    lite = [n for n in ok if "lite" in n and "preview" not in n]
    rest = [n for n in ok if n not in lite]
    ok = rest[:1] + lite[:2] + rest[1:]
    return ok or [GEMINI_MODEL]


def _gemini_call(key: str, model: str, user: str, system: str):
    return requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": key},
        json={"systemInstruction": {"parts": [{"text": system}]},
              "contents": [{"parts": [{"text": user}]}],
              "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3}},
        timeout=100,
    )


def _gemini(user: str, system: str = SYSTEM) -> str:
    """Free tier via Google AI Studio key (no billing); tries models in order, retries overload."""
    key = os.environ["GEMINI_API_KEY"]
    errors = []
    deadline = time.time() + int(os.environ.get("GEMINI_BUDGET_SEC", "360"))  # hard cap per analysis call
    for model in _gemini_candidates(key)[:8]:
        for attempt in range(2):
            if time.time() > deadline:
                raise RuntimeError("Gemini time budget exceeded: " + "; ".join(errors[-6:]))
            try:
                r = _gemini_call(key, model, user, system)
            except requests.RequestException as exc:  # timeout / connection: don't wait on this model again
                errors.append(f"{model}: {type(exc).__name__}")
                break
            if r.ok:
                try:
                    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                    _extract_json(text)  # validate before accepting
                    print(f"[analyze] using {model}")
                    return text
                except Exception as exc:
                    errors.append(f"{model}: bad output ({exc})")
                    break
            errors.append(f"{model}: {r.status_code}")
            if r.status_code in (500, 503):  # transient: wait and retry same model
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code not in (400, 404, 429):
                raise RuntimeError(f"Gemini {r.status_code}: {r.text[:300]}")
            break  # quota / unknown model: next model
    raise RuntimeError("No Gemini model worked: " + "; ".join(errors))


def _claude(user: str, system: str = SYSTEM) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(model=MODEL, max_tokens=8000, system=system,
                                 messages=[{"role": "user", "content": user}])
    return "".join(b.text for b in msg.content if b.type == "text")


def analyze(headlines: list) -> dict:
    lines = "\n".join(f"{i+1}. [{h['source']}] {h['title']} <{h['url']}>" for i, h in enumerate(headlines))
    user = f"כותרות היממה האחרונה:\n{lines}"
    # Gemini (free) by default; Claude only if explicitly selected.
    use_claude = os.environ.get("ANALYSIS_PROVIDER") == "claude" and os.environ.get("ANTHROPIC_API_KEY")
    return _extract_json(_claude(user) if use_claude else _gemini(user))


WEEKLY_SYSTEM = """אתה אנליסט מאקרו בכיר. תקבל את סיכומי הדוחות היומיים של 7 הימים האחרונים (אירועים, חומרה, מניות, ומצב שוק).
כתוב סיכום שבועי בעברית: מה היו הנושאים המרכזיים של השבוע, אילו מגמות מתעצמות או נחלשות, אילו אירועים חזרו על עצמם,
ומה כדאי לעקוב אחריו בשבוע הבא. אל תמציא עובדות שלא מופיעות בנתונים.
החזר JSON תקין בלבד:
{
 "summary": "סיכום מנהלים של 3-4 משפטים",
 "market_mood": "risk-on | risk-off | mixed",
 "themes": [{"title": "", "trend": "מתעצם|נחלש|יציב", "what_happened": "", "market_impact": "",
             "tickers": [{"ticker": "", "note": ""}]}],
 "best_ideas": [{"ticker": "", "name": "", "horizon": "קצר|בינוני|ארוך", "why": ""}],
 "risks": ["סיכונים עיקריים"],
 "watch_next_week": ["אירועים/נקודות מעקב"],
 "regions_to_watch": [{"region": "", "stance": "להעדיף|להיזהר|ניטרלי", "why": ""}],
 "outlook": {"short": "", "medium": "", "long": ""}
}"""


def analyze_weekly(days: list) -> dict:
    """days: list of {"date", "analysis"} dicts, oldest first."""
    parts = []
    for d in days:
        a = d["analysis"]
        evs = "; ".join(
            f"{e.get('title')} (חומרה {e.get('severity')}, {e.get('category')}) מנצחות: "
            + ",".join(w.get("ticker", "") for w in e.get("winners", []))
            for e in a.get("events", []))
        parts.append(f"## {d['date']}\nסיכום: {a.get('summary','')}\nאירועים: {evs}")
    user = "\n\n".join(parts)
    use_claude = os.environ.get("ANALYSIS_PROVIDER") == "claude" and os.environ.get("ANTHROPIC_API_KEY")
    return _extract_json(_claude(user, WEEKLY_SYSTEM) if use_claude else _gemini(user, WEEKLY_SYSTEM))


MARKET_SYSTEM = """אתה אסטרטג שוק הון בכיר. תקבל מדדי שוק עדכניים (מחיר, שינוי יומי/שבועי/חודשי, מרחק משיא שנתי, מול ממוצע 50 יום) וסיכום אירועי היום.
כתוב ניתוח "מצב השוק" בעברית, ענייני ומבוסס על הנתונים שקיבלת בלבד (אל תמציא מספרים).
החזר JSON תקין בלבד:
{
 "headline": "משפט אחד שמסכם את מצב השוק",
 "context": "קונטקסט: מה קרה ולמה (3-4 משפטים), כולל קשר לאירועי היום",
 "analysis": "ניתוח: מגמה, מומנטום, רוחב, תשואות/VIX/דולר/סחורות ומה הם אומרים (4-6 משפטים)",
 "recommendation": "המלצה: סטנס כללי (אגרסיבי/ניטרלי/זהיר) ופעולות קונקרטיות לפי סקטורים",
 "by_horizon": {"short": "", "medium": "", "long": ""},
 "levels_to_watch": ["רמות/אירועים לעקוב אחריהם"],
 "risks": ["סיכונים עיקריים"]
}"""


def analyze_market_state(indices: list, analysis: dict) -> dict:
    ev = "; ".join(f"{e.get('title')} (חומרה {e.get('severity')})" for e in analysis.get("events", []))
    user = ("מדדים:\n" + json.dumps(indices, ensure_ascii=False) +
            f"\n\nסיכום היום: {analysis.get('summary','')}\nאירועים: {ev}")
    return _call(user, MARKET_SYSTEM)


PORTFOLIO_SYSTEM = """אתה יועץ השקעות-אנליסט המנתח תיק אישי. תקבל לכל נייר: משקל בתיק (%), רווח/הפסד ביחס לעלות (%), ומדדים טכניים (שינוי יומי/שבועי/חודשי/3 חודשים, מרחק משיא 52 שבועות, מול ממוצעים נעים, RSI, מחזור יחסי),
וכן סיכום אירועי היום והשוק. אין לך כמויות או סכומים, רק אחוזים.
כללים: הבחן בין עובדה (מהמדדים) להערכה; אל תמציא נתונים פונדמנטליים (דוחות, מכפילים) שלא קיבלת; לניירות ללא נתוני שוק (קרנות/תפ"ס) כתוב ניתוח איכותי לפי סוג הנייר והשוק בלבד וציין שאין נתוני שוק;
לכל נייר המלצה נפרדת לכל טווח, מתוך: "להחזיק", "להגדיל", "להקטין", "למכור", "לעקוב". ההמלצות חייבות להתחשב במשקל (ריכוזיות) וברווח/הפסד.
גודל פעולה: לכל המלצה "להקטין"/"למכור" ציין size_pct = אחוז מהפוזיציה למכור (1-100; "למכור" = 100 אלא אם יש סיבה לחלקי). לכל המלצה "להגדיל" ציין size_pct = אחוז מערך התיק כולו להוסיף (0.5-5, לעולם לא מעל 5). ל"להחזיק"/"לעקוב" size_pct=0.
מחירי כניסה ויציאה: לכל נייר עם נתוני שוק (יש לו price) ציין במחיר המטבע של הנייר: buy_below = מחיר מקסימלי לקנייה/הוספה (פקודת לימיט, בדרך כלל ליד תמיכה כמו ממוצע 50/200 או תיקון), sell_above = יעד למכירה/הקטנה, stop = סטופ-לוס הגנתי. עגן את המחירים ברמות שקיבלת (price, ma50, ma200, high52, low52), בתוך טווח סביר מהמחיר הנוכחי; אל תמציא מחירים. אם אין המלצה להוסיף/להקטין, השאר null. ללא נתוני שוק: null.
יעד: אם סופק יעד, כתוב goal_assessment כנה. אסור להמליץ על מינוף, אופציות, מכירה בחסר או הגדלת ריכוזיות רק כדי להגיע ליעד; אם היעד אינו ריאלי ללא סיכון קיצוני - אמור זאת במפורש. אחרת השאר goal_assessment ריק.
פעולות מרכזיות: 3-5 פעולות לפי עדיפות. כל אחת חייבת להתייחס לנייר אחד (ticker) ולטווח (horizon), ולהתאים בדיוק לפעולה שהמלצת עליה באותו נייר ובאותו טווח (אותה action). אל תכתוב סכומים בטקסט - המערכת תוסיף אותם.
הגיון: אל תמליץ על הוספות גדולות לנייר שכבר ריכוזי בתיק, ואל תמליץ בו-זמנית להגדיל ולהקטין את אותו נייר באותו טווח. הסכומים בשקלים/דולרים יחושבו בנפרד על ידי המערכת.
כתוב בעברית. החזר JSON תקין בלבד:
{
 "summary": "סיכום התיק ב-3-4 משפטים",
 "health": "חזק|בינוני|חלש",
 "positions": [{"ticker": "", "analysis": "2-3 משפטים", "short": {"action": "", "size_pct": 0, "why": ""}, "medium": {"action": "", "size_pct": 0, "why": ""}, "long": {"action": "", "size_pct": 0, "why": ""}, "buy_below": null, "sell_above": null, "stop": null, "levels_note": "על מה מבוססות הרמות", "watch": "מה לעקוב"}],
 "concentration": "ריכוזיות/חשיפה לפי סקטור, מדינה, מטבע",
 "exposure_to_today": "איך אירועי היום משפיעים על התיק",
 "risks": [""],
 "goal_assessment": {"verdict": "הערכה כנה האם היעד ריאלי (אם סופק יעד), ללא ייפוי", "what_must_go_right": "מה צריך לקרות כדי להגיע אליו", "alternatives": ["חלופות: הפקדה, יעד ריאלי יותר, אופק ארוך יותר"]},
 "top_actions": [{"ticker": "", "horizon": "short|medium|long", "text": "הפעולה והסיבה במשפט אחד"}]
}"""


def analyze_portfolio(holdings_view: list, analysis: dict, market_state: dict = None, goal: dict = None) -> dict:
    ev = "; ".join(f"{e.get('title')}: {e.get('impact','')}" for e in analysis.get("events", []))
    user = ("תיק (אחוזים בלבד):\n" + json.dumps(holdings_view, ensure_ascii=False) +
            f"\n\nסיכום היום: {analysis.get('summary','')}\nאירועים: {ev}" +
            (f"\nמצב שוק: {market_state.get('headline','')} {market_state.get('recommendation','')}" if market_state else "") +
            (f"\nיעד המשתמש: נדרשת תשואה של {goal['required_total_pct']}% בתוך {goal['weeks_left']} שבועות (כ-{goal['required_weekly_pct']}% בשבוע ברציפות). "
             f"הוא כרגע {'מעל' if goal['on_track'] else 'מתחת'} לקו ישר אל היעד ({goal['vs_path_pct']:+.1f}%)." if goal else ""))
    return _call(user, PORTFOLIO_SYSTEM)


def _call(user: str, system: str) -> dict:
    use_claude = os.environ.get("ANALYSIS_PROVIDER") == "claude" and os.environ.get("ANTHROPIC_API_KEY")
    return _extract_json(_claude(user, system) if use_claude else _gemini(user, system))
