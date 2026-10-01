"""Send the daily report through Resend."""
import os

import requests


def send(subject: str, html: str):
    key, to = os.environ["RESEND_API_KEY"], os.environ["REPORT_TO_EMAIL"]
    sender = os.environ.get("RESEND_FROM", "Market Watch <onboarding@resend.dev>")
    r = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {key}"},
        json={"from": sender, "to": [to], "subject": subject, "html": html},
        timeout=30,
    )
    r.raise_for_status()
    print("[email] sent:", r.json())
