"""Trend discovery: scan a broad set of sector / industry / theme / country ETFs, rank what is moving,
let the model explain the themes the user is unlikely to follow, then pick stocks from the ETFs' real holdings."""
import math

# ETF -> short Hebrew name. Broad on purpose: the point is to surface themes the user does not already know.
THEMES = {
    "XLE": "אנרגיה (נפט וגז)", "XOP": "הפקת נפט וגז", "OIH": "שירותי שדות נפט", "URA": "אורניום ואנרגיה גרעינית", "TAN": "אנרגיה סולארית",
    "ICLN": "אנרגיה נקייה", "LIT": "ליתיום וסוללות", "UNG": "גז טבעי", "USO": "נפט (חוזים)",
    "XLK": "טכנולוגיה", "SMH": "שבבים", "IGV": "תוכנה", "SKYY": "מחשוב ענן", "BOTZ": "רובוטיקה ובינה מלאכותית", "ARKK": "חדשנות משבשת",
    "CIBR": "סייבר", "DRIV": "רכב חשמלי ואוטונומי", "UFO": "חלל", "BLOK": "בלוקצ'יין", "IBIT": "ביטקוין (קרן)",
    "XLV": "בריאות", "IBB": "ביוטכנולוגיה", "XBI": "ביוטק קטנות", "IHI": "מכשור רפואי",
    "XLF": "פיננסים", "KRE": "בנקים אזוריים", "XLI": "תעשייה", "PAVE": "תשתיות ובנייה", "ITA": "אווירונוטיקה וביטחון", "SHLD": "ביטחון (עולמי)", "JETS": "תעופה",
    "XLB": "חומרי גלם", "XME": "מתכות וכרייה", "COPX": "נחושת", "REMX": "מתכות נדירות", "GDX": "כורי זהב", "SIL": "כסף וכורי כסף", "MOO": "חקלאות",
    "XLU": "חברות חשמל", "XLP": "מוצרי צריכה בסיסיים", "XLY": "צריכה מחזורית", "ITB": "בנייני בתים", "XLRE": "נדל\"ן", "XLC": "תקשורת ומדיה",
    "TLT": "אג\"ח ממשלתי ארוך", "GLD": "זהב",
    "FXI": "סין", "KWEB": "אינטרנט סיני", "EWJ": "יפן", "INDA": "הודו", "EWZ": "ברזיל", "EWY": "דרום קוריאה", "EWT": "טייוואן", "EEM": "שווקים מתפתחים",
}
BENCH = "SPY"


def _pct(close, n):
    return round((float(close.iloc[-1]) / float(close.iloc[-n - 1]) - 1) * 100, 1) if len(close) > n else None


def scan() -> list:
    """Rank all theme ETFs. Returns rows sorted by 3-month relative strength vs SPY."""
    import yfinance as yf
    syms = list(THEMES) + [BENCH]
    d = yf.download(syms, period="1y", interval="1d", progress=False, auto_adjust=True, group_by="ticker", threads=False)
    rows = {}
    for s in syms:
        try:
            c = d[s]["Close"].dropna()
            if len(c) < 100:
                continue
            last = float(c.iloc[-1])
            rows[s] = {"ticker": s, "price": round(last, 2), "w1": _pct(c, 5), "m1": _pct(c, 21), "m3": _pct(c, 63), "m6": _pct(c, 126),
                       "from_52w_high": round((last / float(c.max()) - 1) * 100, 1),
                       "vs_ma200": round((last / float(c.tail(200).mean()) - 1) * 100, 1) if len(c) >= 200 else None}
        except Exception:
            continue
    b = rows.get(BENCH, {})
    out = []
    for s, r in rows.items():
        if s == BENCH:
            continue
        r["name"] = THEMES[s]
        r["rel3"] = round(r["m3"] - b["m3"], 1) if r.get("m3") is not None and b.get("m3") is not None else None
        r["rel1"] = round(r["m1"] - b["m1"], 1) if r.get("m1") is not None and b.get("m1") is not None else None
        # acceleration: last month's pace vs the pace of the previous two months (what is heating up, not just what already ran)
        r["accel"] = round(r["m1"] - (r["m3"] - r["m1"]) / 2, 1) if r.get("m1") is not None and r.get("m3") is not None else None
        out.append(r)
    out.sort(key=lambda x: -(x.get("rel3") if x.get("rel3") is not None else -999))
    return out


def holdings(etf: str, n: int = 8) -> list:
    """Top US-listed holdings of an ETF (symbols without exchange suffix)."""
    try:
        import yfinance as yf
        idx = list(yf.Ticker(etf).funds_data.top_holdings.index)
        return [t for t in idx if t and "." not in t and t.isalpha() and len(t) <= 5][:n]
    except Exception:
        return []


def theme_universe(theme: dict) -> list:
    """Metrics rows for the theme's ETFs plus their top holdings (used to validate the model's picks)."""
    from portfolio import metrics_for
    seen, rows = set(), []
    tickers = list(theme.get("etfs") or [])
    for e in list(tickers):
        tickers += holdings(e)
    for t in tickers:
        t = str(t).upper()
        if t in seen:
            continue
        seen.add(t)
        m = metrics_for(t)
        if m:
            rows.append({"ticker": t, **{k: (round(v, 2) if isinstance(v, float) else v) for k, v in m.items() if v is not None}})
    return rows


def discover(analysis: dict, market_state, retry) -> dict:
    """Full pipeline -> {"summary", "scan_top", "themes": [{name, etfs, stage, explain, why_now, risk, horizon, picks}]}"""
    from analyze import analyze_candidates, analyze_themes
    import candidates
    rows = scan()
    if len(rows) < 10:
        raise RuntimeError("scan returned too little data")
    raw = retry(lambda: analyze_themes(rows, analysis, market_state), "themes")
    known = {r["ticker"] for r in rows}
    themes = []
    for t in (raw.get("themes") or [])[:6]:
        etfs = [e for e in (t.get("etfs") or []) if str(e).upper() in known][:2]
        if not etfs or not t.get("name"):
            continue
        t["etfs"] = [str(e).upper() for e in etfs]
        themes.append(t)
    data = {t["name"]: theme_universe(t) for t in themes}
    picks_raw = retry(lambda: analyze_candidates(data, analysis, market_state), "theme_picks")
    validated = candidates.validate(picks_raw, data)["picks"]
    for t in themes:
        t["picks"] = validated.get(t["name"], [])
        r = next((x for x in rows if x["ticker"] == t["etfs"][0]), {})
        t["stats"] = {k: r.get(k) for k in ("m1", "m3", "rel3", "from_52w_high")}
    leaders = [{"ticker": r["ticker"], "name": r["name"], "m1": r["m1"], "m3": r["m3"], "rel3": r["rel3"]} for r in rows[:5]]
    laggards = [{"ticker": r["ticker"], "name": r["name"], "m1": r["m1"], "m3": r["m3"], "rel3": r["rel3"]} for r in rows[-3:]]
    return {"summary": raw.get("summary"), "leaders": leaders, "laggards": laggards, "themes": themes}
