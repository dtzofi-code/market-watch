"""Private portfolio support.

Holdings come from the PORTFOLIO_JSON secret (or portfolio.local.json for development).
Nothing here is ever written to data/ or docs/ - the output goes to email/Telegram only.
Only percentages (weights, P/L %) are ever sent to the AI, never quantities or amounts.
"""
import json
import os

from render import ROOT

LOCAL = os.path.join(ROOT, "portfolio.local.json")


def load() -> list:
    raw = os.environ.get("PORTFOLIO_JSON")
    if not raw and os.path.exists(LOCAL):
        raw = open(LOCAL, encoding="utf-8").read()
    if not raw:
        return []
    items = json.loads(raw)
    return items["holdings"] if isinstance(items, dict) else items


def _rsi(close, n=14):
    d = close.diff().dropna()
    if len(d) < n:
        return None
    up, dn = d.clip(lower=0).tail(n).mean(), (-d.clip(upper=0)).tail(n).mean()
    return round(100.0 if dn == 0 else 100 - 100 / (1 + up / dn), 0)


def metrics_for(symbol: str):
    """Technical metrics from yfinance, or None if the symbol has no market data."""
    try:
        import yfinance as yf
        h = yf.Ticker(symbol).history(period="1y", interval="1d", auto_adjust=True)
        close = h["Close"].dropna()
        if len(close) < 20:
            return None
        last = float(close.iloc[-1])
        pct = lambda n: round((last / float(close.iloc[-n - 1]) - 1) * 100, 1) if len(close) > n else None
        vol = h["Volume"].dropna()
        return {
            "price": last, "d1": pct(1), "w1": pct(5), "m1": pct(21), "m3": pct(63),
            "from_52w_high": round((last / float(close.max()) - 1) * 100, 1),
            "vs_ma50": round((last / float(close.tail(50).mean()) - 1) * 100, 1) if len(close) >= 50 else None,
            "vs_ma200": round((last / float(close.tail(200).mean()) - 1) * 100, 1) if len(close) >= 200 else None,
            "rsi14": _rsi(close),
            "rel_volume": round(float(vol.iloc[-1]) / float(vol.tail(20).mean()), 1) if len(vol) >= 20 and vol.tail(20).mean() else None,
        }
    except Exception:
        return None


def usd_ils() -> float:
    m = metrics_for("ILS=X")
    return m["price"] if m else 3.7


def build(holdings: list) -> dict:
    """Enrich holdings with market metrics, P/L and weights. Returns {rows, totals}."""
    fx = usd_ils()
    rows = []
    for h in holdings:
        sym = h.get("yf") or (h["ticker"] if h.get("type") in ("stock", "etf") else None)
        m = metrics_for(sym) if sym else None
        cur = h.get("currency", "USD")
        price = m["price"] if m else None
        if price and sym and sym.endswith(".TA"):
            price /= 100  # TASE quotes are in agorot
        qty, cost = h.get("qty"), h.get("cost")
        has_amounts = qty is not None and cost is not None  # amounts are optional: symbols alone still get analysed
        to_usd = (1 / fx) if cur == "ILS" else 1.0
        value = invested = value_usd = invested_usd = pnl = None
        if has_amounts:
            qty, cost = float(qty), float(cost)
            value = qty * price if price else qty * cost  # no market data -> valued at cost
            invested = qty * cost
            value_usd, invested_usd = value * to_usd, invested * to_usd
            pnl = round((value / invested - 1) * 100, 1) if invested else None
        rows.append({
            **{k: h.get(k) for k in ("ticker", "name", "type", "currency")},
            "has_data": bool(m), "m": m or {}, "price": price,
            "value_usd": value_usd, "invested_usd": invested_usd, "pnl_pct": pnl, "weight": None,
        })
    sized = [r for r in rows if r["value_usd"] is not None]
    total = sum(r["value_usd"] for r in sized)
    inv = sum(r["invested_usd"] for r in sized)
    for r in sized:
        r["weight"] = round(r["value_usd"] / total * 100, 1) if total else None
    rows.sort(key=lambda r: -(r["weight"] or 0))
    day = sum((r["m"].get("d1") or 0) * r["value_usd"] / total for r in sized if r["has_data"]) if total else None
    return {"rows": rows, "totals": {
        "pnl_pct": round((total / inv - 1) * 100, 1) if inv else None,
        "day_pct": round(day, 2) if day is not None else None, "fx": round(fx, 2), "n": len(rows),
        "no_data": sum(1 for r in rows if not r["has_data"]), "sized": bool(total),
    }}


def for_ai(pf: dict) -> list:
    """Percent-only view of the portfolio - safe to send to a third-party model."""
    keep = ("d1", "w1", "m1", "m3", "from_52w_high", "vs_ma50", "vs_ma200", "rsi14", "rel_volume")
    return [{"ticker": r["ticker"], "name": r["name"], "type": r["type"], "weight_pct": r["weight"],
             "pnl_pct": r["pnl_pct"], "has_market_data": r["has_data"],
             **{k: r["m"].get(k) for k in keep if r["m"].get(k) is not None}} for r in pf["rows"]]
