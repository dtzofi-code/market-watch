"""Investment candidates by category: market data for a fixed universe + validation of the model's picks."""
from config import CANDIDATES

SIGN = "$"  # the universe is USD-listed only


def gather() -> dict:
    """{category: [{ticker, price, d1, w1, m1, m3, from_52w_high, vs_ma50, vs_ma200, rsi14, ma50, ma200, high52, low52}]}"""
    from portfolio import metrics_for
    out = {}
    for cat, tickers in CANDIDATES.items():
        rows = []
        for t in tickers:
            m = metrics_for(t)
            if m:
                rows.append({"ticker": t, **{k: (round(v, 2) if isinstance(v, float) else v) for k, v in m.items() if v is not None}})
        out[cat] = rows
    return out


def validate(raw: dict, data: dict) -> dict:
    """Keep only picks whose ticker is in the category's universe (max 3); drop price levels that don't make sense."""
    result = {}
    for cat, rows in data.items():
        by = {r["ticker"]: r for r in rows}
        picks = []
        for p in (raw.get("picks", {}) or {}).get(cat, []) or []:
            r = by.get(str(p.get("ticker", "")).upper())
            if not r or any(x["ticker"] == r["ticker"] for x in picks):
                continue
            px = r["price"]
            def lvl(v, lo, hi):
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    return None
                return round(v, 2) if px * lo <= v <= px * hi else None
            picks.append({
                "ticker": r["ticker"], "name": p.get("name") or r["ticker"], "type": p.get("type") or "stock",
                "price": round(px, 2), "d1": r.get("d1"), "w1": r.get("w1"), "m1": r.get("m1"), "from_52w_high": r.get("from_52w_high"),
                "thesis": p.get("thesis"), "horizon": p.get("horizon"), "conviction": p.get("conviction"), "risk": p.get("risk"),
                "buy_below": lvl(p.get("buy_below"), 0.6, 1.02), "target": lvl(p.get("target"), 1.0, 1.8), "stop": lvl(p.get("stop"), 0.4, 0.995),
            })
            if len(picks) == 3:
                break
        result[cat] = picks
    return {"theme": raw.get("theme"), "picks": result}


def personalize(cands: dict, pf: dict) -> dict:
    """Private extras for the e-mail only: existing exposure and how many units the cash can buy."""
    if not (pf and cands):
        return {}
    weights = {r["ticker"]: r["weight"] for r in pf["rows"] if r.get("weight") is not None}
    cash = pf["totals"].get("cash_usd") or 0
    extra = {}
    for picks in cands.get("picks", {}).values():
        for p in picks:
            extra[p["ticker"]] = {"weight": weights.get(p["ticker"]), "units": int(cash // p["price"]) if cash and p["price"] else 0,
                                  "cash": cash}
    return extra
