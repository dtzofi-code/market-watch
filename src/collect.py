"""Collect recent headlines from RSS feeds and GDELT."""
import calendar
import time

import feedparser
import requests

from config import FEEDS, GDELT_QUERY, HOURS_BACK, MAX_HEADLINES

UA = {"User-Agent": "world-events-market-watch/1.0"}


def _from_rss():
    cutoff = time.time() - HOURS_BACK * 3600
    items = []
    for name, url in FEEDS:
        try:
            resp = requests.get(url, headers=UA, timeout=20)
            feed = feedparser.parse(resp.content)
        except Exception as exc:  # one bad source must not sink the report
            print(f"[collect] {name} failed: {exc}")
            continue
        for e in feed.entries[:40]:
            ts = e.get("published_parsed") or e.get("updated_parsed")
            if ts and calendar.timegm(ts) < cutoff:
                continue
            items.append({"source": name, "title": e.get("title", "").strip(), "url": e.get("link", "")})
    return items


def _from_gdelt():
    try:
        resp = requests.get(
            "https://api.gdeltproject.org/api/v2/doc/doc",
            params={"query": GDELT_QUERY + " sourcelang:english", "mode": "ArtList", "format": "json",
                    "maxrecords": 60, "timespan": f"{HOURS_BACK}h", "sort": "hybridrel"},
            headers=UA, timeout=25,
        )
        return [{"source": a.get("domain", "GDELT"), "title": a.get("title", "").strip(), "url": a.get("url", "")}
                for a in resp.json().get("articles", [])]
    except Exception as exc:
        print(f"[collect] GDELT failed: {exc}")
        return []


def collect():
    seen, out = set(), []
    for it in _from_rss() + _from_gdelt():
        key = it["title"].lower()[:70]
        if not it["title"] or key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out[:MAX_HEADLINES]


if __name__ == "__main__":
    for h in collect()[:20]:
        print(h["source"], "|", h["title"])
