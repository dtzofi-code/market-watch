"""Configuration: news sources and the reference map the analyst model uses."""
import os

FEEDS = [
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("Times of Israel", "https://www.timesofisrael.com/feed/"),
    ("Globes", "https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=2"),
    ("Calcalist", "https://www.calcalist.co.il/GeneralRSS/0,16335,L-8,00.xml"),
    ("CNBC Markets", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664"),
    ("Tom's Hardware", "https://www.tomshardware.com/feeds/all"),
    ("TechCrunch", "https://techcrunch.com/feed/"),
    ("Oilprice", "https://oilprice.com/rss/main"),
]

GDELT_QUERY = "(war OR attack OR sanctions OR shortage OR hijack OR blockade OR strike OR outbreak OR embargo)"
HOURS_BACK = 36
MAX_HEADLINES = 150

MODEL = os.environ.get("ANALYSIS_MODEL", "claude-sonnet-5-5")  # only if ANALYSIS_PROVIDER=claude
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Reference examples given to the model so it reasons the way the owner expects.
REFERENCE_MAP = """
- Airline security incident / hijack attempt -> local airline can surge on sympathy/defence-demand (e.g. El Al, ELAL.TA); foreign airlines & travel fall.
- Chip shortage -> semis, memory, storage, disks (NVDA, MU, WDC, STX, SNDK, TSM, ASML, AMAT) rise; auto makers & PC OEMs fall.
- War in Israel / Ukraine -> defence & data/AI-for-defence (PLTR, LMT, RTX, NOC, Elbit ESLT / ESLT.TA, Israel Aerospace-linked, Aryt, Tadiran), gold, oil; airlines, tourism fall.
- Oil / shipping chokepoint disruption -> energy (XOM, CVX, OXY), tankers (FRO, STNG), Israeli Delek/Oil Refineries; airlines & chemicals fall.
- Cyber incident -> CRWD, PANW, FTNT, CHKP, CYBR(.TA peers: Cyberark/Check Point).
- Pandemic / outbreak -> vaccines & diagnostics, remote work, delivery; airlines, cruise, hotels fall.
- Sanctions / trade war -> domestic substitutes, rare earths (MP), gold; exporters exposed to the region fall.
Use Tel Aviv tickers with the .TA suffix and US tickers plain.
"""

# Tickers always shown in the market snapshot.
WATCHLIST = ["^GSPC", "^IXIC", "^TA125.TA", "GC=F", "CL=F", "NVDA", "PLTR", "LMT", "ESLT.TA", "ELAL.TA"]
