import os, re, time, textwrap, html
import requests, feedparser
from bs4 import BeautifulSoup
from dateutil import parser as dtparser
from datetime import datetime, timedelta, timezone

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# --- CONFIG ---
TARGET_CATEGORIES = ["Markets", "UK News", "Global Politics", "VC/PE", "Insurance"]
FALLBACK_CATEGORY = "Light-hearted"
MAX_SENTENCES = 3
LOOKBACK_HOURS = 36  # accept stories from last 36h first

RSS_SOURCES = {
    "Markets": [
        # Financial/global markets
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
        "https://feeds.feedburner.com/pehubblog",   # PE Hub (public posts)
        "https://news.crunchbase.com/feed/",
    ],
    "Insurance": [
        "https://www.insurancejournal.com/rss/ijnational.rss",
        "https://www.insurancetimes.co.uk/XmlServers/navsectionrss.aspx?navsectioncode=News",  # UK
        "https://www.insurancebusinessmag.com/uk/rss/",
    ],
    "Light-hearted": [
        "https://www.reuters.com/lifestyle/oddly-enough/rss",
        "https://feeds.bbci.co.uk/news/newsbeat/rss.xml",
        "https://www.theguardian.com/lifeandstyle/rss",
    ],
}

# --- Helpers ---
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9“\"'])")

def strip_html(text):
    if not text:
        return ""
    text = html.unescape(text)
    return BeautifulSoup(text, "html.parser").get_text(" ", strip=True)

def summarize(text, max_sentences=3, max_chars=420):
    clean = strip_html(text)
    parts = SENTENCE_SPLIT.split(clean)
    if not parts:
        parts = [clean]
    summary = " ".join(parts[:max_sentences]).strip()
    if len(summary) > max_chars:
        summary = summary[:max_chars].rsplit(" ", 1)[0] + "…"
    # Ensure 1–3 short bullet-ish lines for Discord readability
    # We'll keep as plain sentences; Discord will wrap.
    return summary

def parse_time(entry):
    # Try multiple fields
    for key in ("published", "updated"):
        val = entry.get(key) or entry.get(key + "_parsed")
        if val:
            try:
                if isinstance(val, str):
                    return dtparser.parse(val)
                else:
                    # time.struct_time
                    return datetime.fromtimestamp(time.mktime(val), tz=timezone.utc)
            except Exception:
                continue
    return None

def pick_fresh_item(feeds, cutoff_recent, cutoff_any):
    best_recent, best_any = None, None
    seen_titles = set()
    for url in feeds:
        fp = feedparser.parse(url)
        for e in fp.entries[:15]:
            title = strip_html(e.get("title", "")).strip()
            if not title or title.lower() in seen_titles:
                continue
            seen_titles.add(title.lower())
            link = e.get("link") or ""
            desc = e.get("summary") or e.get("description") or ""
            published = parse_time(e) or datetime.now(timezone.utc)  # if unknown, treat as now
            item = {
                "title": title,
                "link": link,
                "desc": desc,
                "published": published.astimezone(timezone.utc),
            }
            if item["published"] >= cutoff_recent:
                if not best_recent or item["published"] > best_recent["published"]:
                    best_recent = item
            if item["published"] >= cutoff_any:
                if not best_any or item["published"] > best_any["published"]:
                    best_any = item
    return best_recent or best_any

def build_embeds(selected):
    embeds = []
    for cat, item in selected:
        if not item:
            continue
        title = item["title"][:250]
        url = item["link"] or None
        desc = summarize(item["desc"], max_sentences=MAX_SENTENCES)
        ts = item["published"].isoformat()
        embeds.append({
            "title": f"{cat}: {title}",
            "url": url,
            "description": desc,
            "timestamp": ts,
            "color": 0x2b6cb0,  # blue
            "footer": {"text": "Daily Briefing"},
        })
    return embeds

def post_to_discord(webhook_url, content, embeds):
    payload = {"content": content, "embeds": embeds}
    r = requests.post(webhook_url, json=payload, timeout=20)
    r.raise_for_status()
    return r.status_code

def main():
    if not DISCORD_WEBHOOK_URL:
        raise SystemExit("Missing DISCORD_WEBHOOK_URL")

    now = datetime.now(timezone.utc)
    cutoff_recent = now - timedelta(hours=LOOKBACK_HOURS)
    cutoff_any = now - timedelta(days=3)  # relaxed if quiet

    selected = []

    # Guarantee five slots; if a category has nothing, we'll try the fallback later.
    for cat in TARGET_CATEGORIES:
        item = pick_fresh_item(RSS_SOURCES[cat], cutoff_recent, cutoff_any)
        selected.append((cat, item))

    # Fill gaps with Light-hearted
    for i, (cat, item) in enumerate(selected):
        if item is None:
            lh_item = pick_fresh_item(RSS_SOURCES[FALLBACK_CATEGORY], cutoff_recent, cutoff_any)
            selected[i] = (FALLBACK_CATEGORY, lh_item if lh_item else None)

    # Keep only items that exist, and trim to 5
    selected = [(c, i) for c, i in selected if i][:5]

    if not selected:
        # As a failsafe, push a simple ping so you notice something is off
        post_to_discord(DISCORD_WEBHOOK_URL, "Daily Briefing: no stories found today.", [])
        return

    date_str = now.astimezone(timezone.utc).strftime("%Y-%m-%d")
    content = f"**Daily News Briefing — {date_str} — 07:00 GMT**"
    embeds = build_embeds(selected)
    post_to_discord(DISCORD_WEBHOOK_URL, content, embeds)

if __name__ == "__main__":
    main()
