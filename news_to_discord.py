import os, time, html
import requests, feedparser
from bs4 import BeautifulSoup
from dateutil import parser as dtparser
from datetime import datetime, timedelta, timezone
import re

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

TARGET_CATEGORIES = ["Markets", "UK News", "Global Politics", "VC/PE", "Insurance"]
FALLBACK_CATEGORY = "Light-hearted"
HEADLINES_PER_CATEGORY = 5
LOOKBACK_HOURS = 36

RSS_SOURCES = {
    "Markets": [
        "https://www.reuters.com/finance/markets/rss",
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "https://finance.yahoo.com/news/rssindex",
    ],
    "UK News": [
        "https://feeds.bbci.co.uk/news/uk/rss.xml",
        "https://www.theguardian.com/uk-news/rss",
        "https://www.reuters.com/world/uk/rss",
    ],
    "Global Politics": [
        "https://www.reuters.com/politics/rss",
        "https://apnews.com/hub/politics?output=rss",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
    ],
    "VC/PE": [
        "https://techcrunch.com/tag/funding/feed/",
        "https://feeds.feedburner.com/pehubblog",
        "https://news.crunchbase.com/feed/",
    ],
    "Insurance": [
        "https://www.insurancejournal.com/rss/ijnational.rss",
        "https://www.insurancetimes.co.uk/XmlServers/navsectionrss.aspx?navsectioncode=News",
        "https://www.insurancebusinessmag.com/uk/rss/",
    ],
    "Light-hearted": [
        "https://www.reuters.com/lifestyle/oddly-enough/rss",
        "https://feeds.bbci.co.uk/news/newsbeat/rss.xml",
        "https://www.theguardian.com/lifeandstyle/rss",
    ],
}

def strip_html(text):
    return BeautifulSoup(html.unescape(text or ""), "html.parser").get_text(" ", strip=True)

def parse_time(entry):
    for key in ("published", "updated"):
        val = entry.get(key) or entry.get(key + "_parsed")
        if val:
            try:
                if isinstance(val, str):
                    return dtparser.parse(val)
                else:
                    return datetime.fromtimestamp(time.mktime(val), tz=timezone.utc)
            except:
                continue
    return None

def get_headlines(feeds, cutoff_recent, cutoff_any, max_items=5):
    headlines = []
    seen = set()
    for url in feeds:
        fp = feedparser.parse(url)
        for e in fp.entries[:20]:
            title = strip_html(e.get("title", "")).strip()
            if not title or title.lower() in seen:
                continue
            seen.add(title.lower())
            pub_time = parse_time(e) or datetime.now(timezone.utc)
            if pub_time >= cutoff_any:
                headlines.append(title)
            if len(headlines) >= max_items:
                return headlines
    return headlines

def main():
    if not DISCORD_WEBHOOK_URL:
        raise SystemExit("Missing DISCORD_WEBHOOK_URL")

    now = datetime.now(timezone.utc)
    cutoff_recent = now - timedelta(hours=LOOKBACK_HOURS)
    cutoff_any = now - timedelta(days=3)

    sections = {}
    for cat in TARGET_CATEGORIES:
        headlines = get_headlines(RSS_SOURCES[cat], cutoff_recent, cutoff_any, HEADLINES_PER_CATEGORY)
        if not headlines:
            headlines = get_headlines(RSS_SOURCES[FALLBACK_CATEGORY], cutoff_recent, cutoff_any, HEADLINES_PER_CATEGORY)
        sections[cat] = headlines

    # Build message
    date_str = now.strftime("%Y-%m-%d")
    lines = [f"**Daily News Briefing — {date_str} — 07:00 GMT**\n"]
    for cat, headlines in sections.items():
        lines.append(f"**{cat}**")
        for h in headlines:
            lines.append(f"- {h}")
        lines.append("")  # blank line after each category

    content = "\n".join(lines)

    # Send to Discord
    r = requests.post(DISCORD_WEBHOOK_URL, json={"content": content})
    r.raise_for_status()

if __name__ == "__main__":
    main()
