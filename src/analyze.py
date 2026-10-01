"""Turn raw headlines into structured market-impact analysis using the Claude API."""
import json
import os
import re

import anthropic

from config import MODEL, REFERENCE_MAP

SYSTEM = f"""אתה אנליסט מאקרו-גיאופוליטי בכיר. תקבל כותרות חדשות מהיממה האחרונה.
משימה: זהה את האירועים והמשברים בעלי השפעה אמיתית על שווקי המניות, קבץ כותרות לאירוע אחד,
והסבר איך כל אירוע משפיע על אזורים, סקטורים ומניות ספציפיות (ארה"ב ותל אביב).

דוגמאות לחשיבה הרצויה:
{REFERENCE_MAP}

כללים:
- התעלם מרעש (ספורט, תרבות, פוליטיקה פנימית ללא השפעה כלכלית).
- אל תמציא עובדות שאינן בכותרות; הסק השפעות רק מתוך הכותרות והידע הכללי שלך.
- בחר 3-8 אירועים, מהחשוב לפחות חשוב. אם אין דבר משמעותי החזר events ריק.
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


def analyze(headlines: list) -> dict:
    lines = "\n".join(f"{i+1}. [{h['source']}] {h['title']} <{h['url']}>" for i, h in enumerate(headlines))
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model=MODEL, max_tokens=8000, system=SYSTEM,
        messages=[{"role": "user", "content": f"כותרות היממה האחרונה:\n{lines}"}],
    )
    return _extract_json("".join(b.text for b in msg.content if b.type == "text"))
