# news_to_discord.py
import os, time, html, re, sys
import requests, feedparser
from bs4 import BeautifulSoup
from dateutil import parser as dtparser
from datetime import datetime, timedelta, timezone

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# --- CONFIG ---
TARGET_CATEGORIES = ["Markets", "UK News", "Global Politics", "VC/PE", "Insurance"]
FALLBACK_CATEGORY = "Light-hearted"
HEADLINES_PER_CATEGORY = 3
LOOKBACK_DAYS = 3
MAX_SUMMARY_CHARS = 520
ENABLE_ARTICLE_FETCH = False  # <- set True if you want deeper summaries (can 403/timeout on some sites)

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
URL_RE = re.compile(r"http[s]?://\S+")

def log(*args):
    print("[news]", *args, file=sys.stdout, flush=True)

def strip_html(text: str) -> str:
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
            except Exception:
                continue
    return None

def fetch_article_text(url: str, timeout=8) -> str:
    if not ENABLE_ARTICLE_FETCH or not url:
        return ""
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 (DailyBrief/1.0)"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
            tag.decompose()
        container = soup.find("article") or soup.body
        ps = (container.find_all("p") if container else []) or soup.find_all("p")
        text = " ".join(p.get_text(" ", strip=True) for p in ps)
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"(Subscribe|Sign up|Cookies|Advertisement).*$", "", text, flags=re.IGNORECASE)
        return text[:6000]
    except Exception as e:
        log("fetch_article_text error:", e)
        return ""

def summarize(text: str, max_sentences=3, max_chars=MAX_SUMMARY_CHARS) -> str:
    clean = strip_html(text)
    if not clean:
        return ""
    parts = SENTENCE_SPLIT.split(clean)
    picked = " ".join(parts
