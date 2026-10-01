"""
Scraper for arenascan.com. Usage: python scraper.py [pages]   (default 5)

Reads  reading.json     your reading list (export it from the site) + dismissed titles
Writes releases.json    latest chapter for titles in your reading list ONLY
       new-titles.json  new series with fewer than 10 chapters, not tracked, not dismissed
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://arenascan.com"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}
DIR = os.path.dirname(os.path.abspath(__file__))
READING, RELEASES, NEW = (os.path.join(DIR, f) for f in ("reading.json", "releases.json", "new-titles.json"))
SHORT = 10        # "new title" means fewer chapters than this
MAX_LOOKUPS = 40  # series pages opened per run
KEEP_DAYS = 30    # new titles not seen on the listing any more are dropped after this
FMT = "%Y-%m-%dT%H:%M:%SZ"


def now():
    return datetime.now(timezone.utc).strftime(FMT)


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get(url):
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.text
            print(f"   [-] HTTP {r.status_code} for {url}")
            if r.status_code == 404:
                return None
        except requests.RequestException as e:
            print(f"   [-] {e}")
        time.sleep(2 * (attempt + 1))
    return None


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", re.sub(r"['’]", "", (s or "").lower()))


def slug_of(url):
    m = re.search(r"/manga/([^/]+)", urlparse(url or "").path)
    return m.group(1) if m else ""


def chapter_no(url="", text=""):
    """Chapter from '-chapter-12-5' in the URL, else clear text. 0.0 if unknown."""
    m = re.search(r"-chapter-(\d+(?:[.-]\d+)?)/?", url or "", re.I)
    if m:
        return float(m.group(1).replace("-", "."))
    text = re.sub(r"(?:hours?|days?|mins?|minutes?|weeks?|ago).*$", "", text or "", flags=re.I)
    m = re.search(r"(?:chapter|ch|ep|episode)[\s.:#\-_]*(\d+(?:\.\d+)?)", text, re.I)
    if m:
        return float(m.group(1))
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*", text)
    return float(m.group(1)) if m else 0.0


def chapter_url(url, series_url, title, num):
    if url.startswith("http") and "/manga/" not in url:
        return url
    slug = slug_of(series_url) or re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    suffix = str(int(num)) if num == int(num) else str(num).replace(".", "-")
    return f"{BASE}/{slug}-chapter-{suffix}/"


def scrape_page(page):
    url = BASE + "/" if page == 1 else f"{BASE}/page/{page}/"
    print(f"[*] Page {page}: {url}")
    html = get(url)
    if not html:
        return []
    cards = BeautifulSoup(html, "html.parser").select(".bsx")
    print(f"    {len(cards)} cards")
    out = []
    for card in cards:
        t = card.select_one(".tt") or card.select_one("a[title]")
        title = (t.get_text(" ", strip=True) or t.get("title", "")) if t else ""
        a = card.select_one("a[href*='/manga/']") or card.select_one("a[href]")
        if not title or not a:
            continue
        series_url = urljoin(BASE, a["href"].strip())
        best_url, best = "", 0.0
        for link in card.select("a[href*='-chapter-'], a[href*='/chapter/']"):
            n = chapter_no(link["href"], link.get_text(strip=True))
            if n >= best:
                best, best_url = n, urljoin(BASE, link["href"].strip())
        if not best:
            ch = card.select_one(".epxs") or card.select_one(".chapter") or card.select_one(".epx")
            best = chapter_no("", ch.get_text(strip=True) if ch else "")
        cover, img = "", card.select_one("img")
        for attr in ("src", "data-src", "data-lazy-src"):
            v = (img.get(attr) or "").strip() if img else ""
            if v and not v.startswith("data:"):
                cover = urljoin(BASE, v)
                break
        sid = slug_of(series_url) or re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        if sid:
            out.append({"id": sid, "title": title, "series_url": series_url, "cover_url": cover,
                        "latest_chapter": best, "latest_chapter_title": f"Chapter {best:g}" if best else "",
                        "latest_chapter_url": chapter_url(best_url, series_url, title, best or 1.0)})
    return out


def series_info(series_url):
    """Chapter count, highest chapter and its link from a series page, or None."""
    html = get(series_url)
    items = BeautifulSoup(html, "html.parser").select("#chapterlist li, .eplister li, .clx li") if html else []
    if not items:
        return None
    best, best_url = 0.0, ""
    for li in items:
        a = li.select_one("a[href]")
        href = urljoin(BASE, a["href"]) if a else ""
        n = chapter_no(href, li.get_text(" ", strip=True))
        if n >= best:
            best, best_url = n, href
    return {"total": int(max(len(items), best)), "latest": best, "url": best_url}


def load_reading():
    data = read_json(READING, {})
    dismissed = set(data.get("dismissed", [])) if isinstance(data, dict) else set()
    items = data.get("reading", data) if isinstance(data, dict) else data
    items = list(items.values()) if isinstance(items, dict) else items
    return [i for i in items if isinstance(i, dict) and i.get("title")], dismissed


def main():
    pages = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 5
    reading, dismissed = load_reading()
    print(f"=== {len(reading)} reading titles, {len(dismissed)} dismissed, {pages} pages ===")

    cards = {}
    for p in range(1, pages + 1):
        for c in scrape_page(p):
            if c["id"] not in cards or c["latest_chapter"] > cards[c["id"]]["latest_chapter"]:
                cards[c["id"]] = c
        time.sleep(1)
    if not cards:
        print("[!] Nothing scraped. The site may be blocking requests or its HTML changed.")
        sys.exit(1)

    stamp, lookups = now(), 0
    prev_rel = {i["id"]: i for i in read_json(RELEASES, []) if isinstance(i, dict) and "id" in i}

    # 1) Reading list: latest chapter for tracked titles only
    tracked, matched, releases = set(), set(), []
    for item in reading:
        iid = item.get("id") or slug_of(item.get("series_url")) or norm(item["title"])
        keys = {iid, norm(item["title"]), slug_of(item.get("series_url"))} - {""}
        tracked |= keys
        card = next((c for c in cards.values() if c["id"] in keys or norm(c["title"]) in keys), None)
        info = None
        if card:
            matched.add(card["id"])
        elif item.get("series_url") and lookups < MAX_LOOKUPS:  # not on the listing pages
            lookups += 1
            info = series_info(item["series_url"])
            time.sleep(0.5)
        old = prev_rel.get(iid, {})
        latest = card["latest_chapter"] if card else (info["latest"] if info else 0.0)
        if not latest:
            if old:
                releases.append(old)  # keep last known data when nothing could be read
            continue
        entry = {
            "id": iid, "title": item["title"],
            "series_url": (card or {}).get("series_url") or item.get("series_url", ""),
            "cover_url": (card or {}).get("cover_url") or old.get("cover_url") or item.get("cover_url", ""),
            "latest_chapter": latest,
            "latest_chapter_title": f"Chapter {latest:g}",
            "latest_chapter_url": (card or {}).get("latest_chapter_url") or (info or {}).get("url") or old.get("latest_chapter_url", ""),
            "updated_at": stamp if latest > old.get("latest_chapter", 0) else old.get("updated_at", stamp),
        }
        releases.append(entry)

    # 2) New titles: fewer than 10 chapters, not tracked, not dismissed
    prev_new = {i["id"]: i for i in read_json(NEW, []) if isinstance(i, dict) and "id" in i}
    new = {}
    for c in cards.values():
        if c["id"] in matched or c["id"] in tracked or norm(c["title"]) in tracked or c["id"] in dismissed:
            continue
        if not 0 < c["latest_chapter"] < SHORT:
            continue
        prev = prev_new.get(c["id"])
        total = prev.get("total_chapters") if prev else None
        if (prev is None or c["latest_chapter"] > prev.get("latest_chapter", 0)) and lookups < MAX_LOOKUPS:
            lookups += 1
            info = series_info(c["series_url"])
            total = info["total"] if info else int(c["latest_chapter"])
            time.sleep(0.5)
        if total is not None and total >= SHORT:
            continue
        new[c["id"]] = {**(prev or {}), **c, "total_chapters": total if total is not None else int(c["latest_chapter"]),
                        "first_seen": (prev or {}).get("first_seen", stamp)}
    cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
    for pid, prev in prev_new.items():  # keep unseen ones for a while
        if pid in new or pid in cards or pid in tracked or pid in dismissed or norm(prev.get("title")) in tracked:
            continue
        try:
            if datetime.strptime(prev["first_seen"], FMT).replace(tzinfo=timezone.utc) > cutoff:
                new[pid] = prev
        except (KeyError, ValueError):
            pass

    write_json(RELEASES, sorted(releases, key=lambda x: x.get("updated_at", ""), reverse=True))
    write_json(NEW, sorted(new.values(), key=lambda x: x.get("first_seen", ""), reverse=True))
    print(f"[+] releases.json: {len(releases)} reading titles | new-titles.json: {len(new)} under {SHORT} chapters")


if __name__ == "__main__":
    main()
