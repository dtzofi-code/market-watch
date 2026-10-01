# מעקב אירועים ושוק המניות

צינור יומי: איסוף כותרות (RSS + GDELT) ← ניתוח עם Gemini (שכבה חינמית; Claude אופציונלי) ← נתוני שוק (yfinance) ← אתר סטטי + מייל (Resend).

## הרצה מקומית
```bash
pip install -r requirements.txt
python src/main.py --demo        # נתוני הדגמה, בלי מפתחות; פותח docs/index.html
GEMINI_API_KEY=... python src/main.py --no-email
```

## פריסה (GitHub Actions + Pages)
1. צור ריפו, דחוף את הקוד.
2. Settings → Pages → Source: **GitHub Actions**.
3. Settings → Secrets → Actions: `GEMINI_API_KEY` (חינמי מ-aistudio.google.com/apikey), `RESEND_API_KEY`, `REPORT_TO_EMAIL`.
4. Actions → daily-report → Run workflow לבדיקה. אחר כך רץ כל יום ~06:30.

הערה: ללא דומיין מאומת ב-Resend, השולח `onboarding@resend.dev` יכול לשלוח רק לכתובת בעלת החשבון. להגדרת שולח אחר: `RESEND_FROM`.

## טלגרם (אופציונלי)
1. ב-Telegram פתח את @BotFather ← `/newbot` ← קבל טוקן.
2. שלח הודעה כלשהי לבוט החדש שלך.
3. העתק את הטוקן והרץ `pbpaste | gh secret set TELEGRAM_BOT_TOKEN -R <owner>/market-watch`.
4. מצא את ה-chat id ב-`https://api.telegram.org/bot<TOKEN>/getUpdates` (שדה `chat.id`) והגדר `TELEGRAM_CHAT_ID` באותו אופן.
