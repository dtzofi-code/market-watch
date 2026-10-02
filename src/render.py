"""Render the website and email HTML from analysis + market data."""
import glob
import os
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env = Environment(loader=FileSystemLoader(os.path.join(ROOT, "src", "templates")),
                  autoescape=select_autoescape(["html", "j2"]))


def OUT():
    """Output root; demo mode redirects here so it never overwrites real reports."""
    return os.environ.get("DEMO_OUT", ROOT)


def _fmt(date: str) -> str:
    return datetime.strptime(date, "%Y-%m-%d").strftime("%d/%m/%Y")


def render(analysis: dict, market: dict, date: str, pf=None, pa=None) -> dict:
    ctx = {"a": analysis, "m": market, "date": _fmt(date)}
    docs = os.path.join(OUT(), "docs")
    os.makedirs(os.path.join(docs, "archive"), exist_ok=True)

    # archive page for this day (links back one level), then the index with archive list
    archive = env.get_template("index.html.j2").render(**ctx, prefix="../", archive=[])
    with open(os.path.join(docs, "archive", f"{date}.html"), "w", encoding="utf-8") as f:
        f.write(archive)

    dates = sorted((os.path.basename(p)[:-5] for p in glob.glob(os.path.join(docs, "archive", "*.html"))), reverse=True)
    index = env.get_template("index.html.j2").render(**ctx, prefix="", archive=[(d, _fmt(d)) for d in dates])
    with open(os.path.join(docs, "index.html"), "w", encoding="utf-8") as f:
        f.write(index)

    email = env.get_template("email.html.j2").render(**ctx, pf=pf, pa=pa, site_url=os.environ.get("SITE_URL", ""))
    return {"email_html": email}


def render_weekly(analysis: dict, market: dict, date: str, start: str, pf=None, pa=None) -> dict:
    ctx = {"a": analysis, "m": market, "range": f"{_fmt(start)} – {_fmt(date)}"}
    wdir = os.path.join(OUT(), "docs", "weekly")
    os.makedirs(wdir, exist_ok=True)
    tpl = env.get_template("weekly.html.j2")
    with open(os.path.join(wdir, f"{date}.html"), "w", encoding="utf-8") as f:
        f.write(tpl.render(**ctx, prefix="../", archive=[]))
    dates = sorted((os.path.basename(p)[:-5] for p in glob.glob(os.path.join(wdir, "*.html"))), reverse=True)
    with open(os.path.join(OUT(), "docs", "weekly.html"), "w", encoding="utf-8") as f:
        f.write(tpl.render(**ctx, prefix="", archive=[(d, _fmt(d)) for d in dates]))
    email = env.get_template("weekly_email.html.j2").render(**ctx, pf=pf, pa=pa, site_url=os.environ.get("SITE_URL", ""))
    return {"email_html": email}
