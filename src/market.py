"""Market snapshot via yfinance: did the market already react?"""
from config import WATCHLIST


def tickers_from(analysis: dict) -> list:
    t = []
    for ev in analysis.get("events", []):
        for s in ev.get("winners", []) + ev.get("losers", []):
            if s.get("ticker"):
                t.append(s["ticker"].strip())
    return list(dict.fromkeys(t + WATCHLIST))


def snapshot(tickers: list) -> dict:
    """Return {ticker: {price, day, week}} (percent changes). Missing data is skipped."""
    try:
        import yfinance as yf
    except ImportError:
        return {}
    out = {}
    try:
        data = yf.download(tickers, period="10d", interval="1d", progress=False,
                           group_by="ticker", auto_adjust=True, threads=True)
    except Exception as exc:
        print(f"[market] download failed: {exc}")
        return {}
    for t in tickers:
        try:
            close = (data[t]["Close"] if len(tickers) > 1 else data["Close"]).dropna()
            if len(close) < 2:
                continue
            last = float(close.iloc[-1])
            out[t] = {
                "price": round(last, 2),
                "day": round((last / float(close.iloc[-2]) - 1) * 100, 1),
                "week": round((last / float(close.iloc[max(-6, -len(close))]) - 1) * 100, 1),
            }
        except Exception:
            continue
    return out
