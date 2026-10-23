"""Portfolio file importer.

Accepts a broker export or a generic file and returns {"holdings": [...], "goal": {...} | None, "warnings": [...]}.
Supported: .json (native), .csv, .xlsx / .xlsm. Column names are matched by alias (English or Hebrew),
so most exports work without editing. Unknown tickers are reported as warnings, never guessed.

Native holding fields: ticker, name, type (stock|etf|fund|bond|cash), qty, cost (per unit), currency,
and optional: yf (Yahoo symbol), last_price, hold, ignore, group.

CLI:  python src/importer.py my_portfolio.xlsx           -> prints a summary
      python src/importer.py my_portfolio.xlsx -o p.json  -> writes the native JSON
"""
import csv
import io
import json
import os
import re
import sys

ALIASES = {
    "id": ("id", "isin", "מספר נייר"),
    "symbol": ("symbol", "ticker", "סימול המניה", "סימול", "סימבול"),
    "name": ("name", "שם נייר", "שם"),
    "qty": ("quantity", "qty", "shares", "units", "כמות", "כמות נוכחית"),
    "cost": ("avg_cost", "cost", "avg_price", "average_cost", "מחיר עלות", "מחיר ממוצע במטבע מקור"),
    "total_cost": ("total_cost", "עלות כוללת", "עלות"),
    "price": ("last_price", "price", "מחיר אחרון", "שער"),
    "currency": ("currency", "מטבע"),
    "type": ("type", "סוג נייר"),
    "hold": ("hold",),
    "ignore": ("ignore",),
    "group": ("group",),
}
KNOWN_ETFS = {"SPY", "QQQ", "VOO", "VTI", "IVV", "IWM", "DIA", "XLE", "XLK", "XLV", "XLF", "SMH", "SOXX", "GLD", "SLV", "TLT", "IBIT", "ARKK"}


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "").replace("‬", "").replace("‪", "").replace("‏", "")).strip().lower()


def _num(x):
    if x is None or x == "":
        return None
    try:
        return float(str(x).replace(",", "").replace("%", "").strip())
    except ValueError:
        return None


def _truthy(x) -> bool:
    return str(x).strip().lower() in ("1", "true", "yes", "y", "כן", "x")


def _rows_from_csv(text: str) -> list:
    rows = list(csv.reader(io.StringIO(text)))
    return [r for r in rows if any(c.strip() for c in r)]


def _rows_from_xlsx(path: str) -> list:
    try:
        import openpyxl
    except ImportError:
        raise SystemExit("Reading .xlsx needs openpyxl:  pip install openpyxl  (or export the file as CSV)")
    ws = openpyxl.load_workbook(path, data_only=True).active
    return [list(r) for r in ws.iter_rows(values_only=True) if any(c not in (None, "") for c in r)]


def _table(rows: list) -> list:
    """Find the header row (the first row containing a known column name) and return a list of dicts."""
    wanted = {a for al in ALIASES.values() for a in al}
    for i, r in enumerate(rows):
        if sum(1 for c in r if _norm(c) in wanted) >= 2:
            head = [_norm(c) for c in r]
            return [{head[j]: (row[j] if j < len(row) else None) for j in range(len(head))} for row in rows[i + 1:]]
    raise ValueError("Could not find a header row. Expected columns such as: symbol, quantity, avg_cost, currency")


def _pick(row: dict, key: str):
    for a in ALIASES[key]:
        v = row.get(_norm(a))
        if v not in (None, ""):
            return v
    return None


def _symbol_from_name(name: str):
    n = _norm(name).upper()
    m = re.search(r"\(([A-Z][A-Z.\-]{0,5})\)?\s*$", n)  # "NVIDIA(NVDA)", also with a missing closing paren
    if m:
        return m.group(1)
    m = re.match(r"^([A-Z]{1,5}) US$", n)  # "HUT US"
    if m:
        return m.group(1)
    m = re.match(r"^([A-Z]{2,5})\b", n)  # "ESLT <hebrew name>", "AMZN <hebrew name>"
    return m.group(1) if m else None


def _currency(v) -> str:
    s = _norm(v)
    if "דולר" in s or "usd" in s or "$" in s:
        return "USD"
    if "שקל" in s or "ils" in s or "nis" in s or "₪" in s:
        return "ILS"
    return "USD"


def _type(raw, symbol) -> str:
    s = _norm(raw)
    if "מזומן" in s or s == "cash":
        return "cash"
    if "תפ\"ס" in s or "אג\"ח" in s or "bond" in s:
        return "bond"
    if "זרות" in s or "etf" in s:
        return "etf"
    if "קרנות" in s or "fund" in s:
        return "etf" if symbol in KNOWN_ETFS else "fund"
    if s in ("stock", "etf", "fund", "bond"):
        return s
    return "etf" if symbol in KNOWN_ETFS else "stock"


def from_rows(rows: list, symbol_map: dict = None) -> dict:
    symbol_map = {_norm(k): v for k, v in (symbol_map or {}).items()}
    out, warnings = [], []
    for r in _table(rows):
        name = str(_pick(r, "name") or "").replace("\u202c", "").strip()
        sym = str(_pick(r, "symbol") or "").strip().upper() or None
        key_sym = sym
        sym = symbol_map.get(_norm(name)) or symbol_map.get(_norm(key_sym)) or sym or _symbol_from_name(name)
        qty = _num(_pick(r, "qty"))
        if not qty or qty <= 0:
            continue
        cur = _currency(_pick(r, "currency"))
        typ = _type(_pick(r, "type"), sym)
        cost, total, price = _num(_pick(r, "cost")), _num(_pick(r, "total_cost")), _num(_pick(r, "price"))
        if typ == "cash":
            cur = _currency(name) if re.search(r"דולר|usd|שקל|ils", _norm(name)) else cur  # the row's own name says which currency it is
            out.append({"ticker": cur, "name": "מזומן " + ("דולרי" if cur == "USD" else "שקלי"), "type": "cash", "qty": qty, "cost": 1.0,
                        "currency": cur, "last_price": 1.0})
            continue
        if price == 0 and not (cost or total):
            continue  # nothing held of any value (e.g. an empty tax-shield instrument)
        if not cost and total:
            cost = total / qty
        pid = str(_pick(r, "id") or "").strip()
        ascii_sym = bool(sym) and sym.isascii()
        h = {"ticker": (sym if ascii_sym else None) or pid or name, "name": name or sym, "type": typ, "qty": qty,
             "cost": round(cost, 4) if cost else None, "currency": cur}
        if ascii_sym and not sym.isdigit():
            h["yf"] = sym + ".TA" if (cur == "ILS" and "." not in sym) else sym
        elif typ in ("stock", "etf"):
            hint = f" (TASE symbol '{sym}')" if sym and not ascii_sym else ""
            warnings.append(f"'{name}'{hint}: no Yahoo ticker found. Map it, e.g. SYMBOL_MAP_FILE with {{\"{name}\": \"<TICKER>.TA\"}}. It is valued at the last price, without market data.")
        if price is not None:
            h["last_price"] = price / 100 if (cur == "ILS" and typ != "cash") else price  # TASE quotes are in agorot
        for k in ("hold", "ignore"):
            if _truthy(_pick(r, k)):
                h[k] = True
        g = _pick(r, "group")
        if g:
            h["group"] = str(g)
        out.append(h)
    return {"holdings": out, "goal": None, "warnings": warnings}


def load_file(path: str, symbol_map: dict = None) -> dict:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        data = json.load(open(path, encoding="utf-8"))
        return {"holdings": data["holdings"] if isinstance(data, dict) else data, "goal": data.get("goal") if isinstance(data, dict) else None, "warnings": []}
    if ext in (".xlsx", ".xlsm"):
        rows = _rows_from_xlsx(path)
    else:
        rows = _rows_from_csv(open(path, encoding="utf-8-sig").read())
    sm_path = os.environ.get("SYMBOL_MAP_FILE")
    if symbol_map is None and sm_path and os.path.exists(sm_path):
        symbol_map = json.load(open(sm_path, encoding="utf-8"))
    return from_rows(rows, symbol_map)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    res = load_file(sys.argv[1])
    for h in res["holdings"]:
        print(f"{h['ticker']:>10}  {h['type']:5} {h['currency']}  qty {h['qty']:<10} cost {h['cost']}  yf={h.get('yf')}")
    for w in res["warnings"]:
        print("WARNING:", w)
    if "-o" in sys.argv:
        json.dump({"holdings": res["holdings"]}, open(sys.argv[sys.argv.index("-o") + 1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
