"""Consolidated action plan: one reconciled list of what to buy / sell, from the portfolio analysis, today's events,
market trends and (weekly) best ideas. Built deterministically so the report never contradicts itself."""

CONV = {"גבוהה": 3, "בינונית": 2, "נמוכה": 1}
STAGE = {"מוקדם": 1.0, "באמצע": 0.5, "מאוחר": -0.5, "נמתח יתר": -1.0}
SELL_ACTIONS = ("למכור", "להקטין")
MAX_WEIGHT = 12.0  # don't suggest adding to something that is already this concentrated (% of portfolio)


def holding_notes(pf: dict, pa: dict) -> dict:
    """{ticker: {weight, stance, avoid_add, reason}} for every held position (private; e-mail only)."""
    if not (pf and pa):
        return {}
    pos_by = {p.get("ticker"): p for p in pa.get("positions", [])}
    out = {}
    for r in pf["rows"]:
        if r.get("weight") is None or r.get("type") == "cash":
            continue
        short = ((pos_by.get(r["ticker"]) or {}).get("short") or {}).get("action")
        sell = short in SELL_ACTIONS and not r.get("hold")
        conc = r["weight"] >= MAX_WEIGHT
        out[r["ticker"]] = {"weight": round(r["weight"], 1), "stance": short, "avoid_add": sell or conc,
                            "reason": "מומלץ להקטין בתיק" if sell else ("כבר מרוכז בתיק" if conc else None)}
    return out


def build(analysis: dict, pf: dict, pa: dict, hn: dict) -> dict:
    """Return {sells, buys, avoid, cash_usd, proceeds_usd, funds_usd} or {} when there is nothing to show."""
    if not (pf and pa):
        return {}
    rows = {r["ticker"]: r for r in pf["rows"]}
    pos_by = {p.get("ticker"): p for p in pa.get("positions", [])}

    # --- sells / reductions (short horizon, never for positions the user chose to hold) ---
    sells, sell_tickers = [], set()
    for t, pos in pos_by.items():
        h = pos.get("short") or {}
        if h.get("action") in SELL_ACTIONS and t in rows and not rows[t].get("hold"):
            sell_tickers.add(t)
            sells.append({"ticker": t, "name": rows[t].get("name") or t, "action": h["action"], "size_text": h.get("size_text"),
                          "size_usd": h.get("size_usd") or 0, "why": h.get("why"), "levels": pos.get("levels_text")})
    sells.sort(key=lambda x: -x["size_usd"])

    # --- buy candidates from every source ---
    cands = {}

    def add(t, name, score, why, source, levels=None, price=None):
        t = str(t or "").upper()
        if not t or "." in t:  # US-listed only (funds are held in USD)
            return
        c = cands.setdefault(t, {"ticker": t, "name": name or t, "score": 0.0, "why": why, "sources": [], "levels": levels, "price": price})
        c["score"] += score
        if source not in c["sources"]:
            c["sources"].append(source)
        if levels and not c.get("levels"):
            c["levels"] = levels
        if price and not c.get("price"):
            c["price"] = price

    for t, pos in pos_by.items():
        h = pos.get("short") or {}
        if h.get("action") == "להגדיל":
            add(t, rows.get(t, {}).get("name"), 4.0, h.get("why"), "ניתוח התיק", pos.get("levels_text"))
    for th in (analysis.get("trends") or {}).get("themes", []):
        for p in th.get("picks", []):
            lv = " · ".join(x for x in (f"קנייה עד ${p['buy_below']:.2f}" if p.get("buy_below") else "", f"יעד ${p['target']:.2f}" if p.get("target") else "",
                                        f"סטופ ${p['stop']:.2f}" if p.get("stop") else "") if x)
            add(p["ticker"], p.get("name"), 1.0 + CONV.get(p.get("conviction"), 1) + STAGE.get(th.get("stage"), 0), p.get("thesis"),
                f"מגמה: {th.get('name')}", lv, p.get("price"))
    for cat, picks in ((analysis.get("candidates") or {}).get("picks") or {}).items():
        for p in picks:
            add(p["ticker"], p.get("name"), 1.0 + CONV.get(p.get("conviction"), 1), p.get("thesis"), f"קטגוריה: {cat}", None, p.get("price"))
    for e in analysis.get("events", []):
        for w in e.get("winners", []):
            add(w.get("ticker"), w.get("name"), 0.5 * CONV.get(w.get("confidence"), 1) + 0.3 * float(e.get("severity") or 0), w.get("reason"),
                f"אירוע: {e.get('title')}")
    for i in analysis.get("best_ideas", []):
        add(i.get("ticker"), i.get("name"), 3.0, i.get("why"), "סיכום שבועי")

    # --- reconcile: never suggest adding what the portfolio analysis says to reduce, or what is already concentrated ---
    avoid, buys = [], []
    for t, c in sorted(cands.items(), key=lambda kv: -kv[1]["score"]):
        note = hn.get(t)
        if note and note.get("avoid_add"):
            avoid.append({"ticker": t, "name": c["name"], "reason": f"{note['reason']} ({note['weight']}% מהתיק) – למרות שמופיע כהזדמנות ב: {', '.join(c['sources'][:2])}"})
        elif len(buys) < 5:
            buys.append(c)

    for b in buys:  # make sure every suggestion has a live price so an amount/units can be computed
        if not b.get("price"):
            r = rows.get(b["ticker"])
            if r and r.get("price"):
                b["price"] = r["price"]
            else:
                try:
                    from portfolio import metrics_for
                    m = metrics_for(b["ticker"])
                    b["price"] = round(m["price"], 2) if m else None
                except Exception:
                    b["price"] = None
    cash = pf["totals"].get("cash_usd") or 0
    proceeds = sum(s["size_usd"] for s in sells)
    funds = cash + proceeds
    total_score = sum(b["score"] for b in buys) or 1.0
    for b in buys:
        b["held"] = (hn.get(b["ticker"]) or {}).get("weight")
        share = min(b["score"] / total_score, 0.4)
        usd = round(funds * share / 5) * 5 if funds >= 25 else 0
        if usd and b.get("price"):
            b["amount_text"] = f"≈ ${usd:,.0f} (≈ {usd / b['price']:.2f} יח׳, אפשר גם חלק מיחידה)"
        elif usd:
            b["amount_text"] = f"≈ ${usd:,.0f} (אפשר גם חלק מיחידה)"
        else:
            b["amount_text"] = "אין תקציב פנוי כרגע – אפשר לממן ממכירות/הקטנות או מהפקדה"
    return {"sells": sells, "buys": buys, "avoid": avoid[:5], "cash_usd": cash, "proceeds_usd": proceeds, "funds_usd": funds}
