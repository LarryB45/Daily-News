# news_to_discord.py
import os, time, html, re
import requests, feedparser
from bs4 import BeautifulSoup
from dateutil import parser as dtparser
from datetime import datetime, timedelta, timezone

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# --- CONFIG ---
TARGET_CATEGORIES = ["Markets", "UK News", "Global Politics", "VC/PE", "Insurance"]
FALLBACK_CATEGORY = "Light-hearted"
HEADLINES_PER_CATEGORY = 3
LOOKBACK_HOURS = 36  # prefer items within last 36h
MAX_SUMMARY_CHARS = 520   # keep summaries tight for Discord

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

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9“\"'])")

def strip_html(text: str) -> str:
    return BeautifulSoup(html.unescape(text or ""), "html.parser").get_text(" ", strip=True)

def parse_time(entry):
    for key in ("published", "updated"):
