import datetime
import os

import requests

TIMEOUT = 30
USER_AGENT = "ai-influencer/1.0"


def _get_json(url, *, params=None, headers=None, timeout=TIMEOUT):
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if data is None:
        raise ValueError("Empty JSON response")
    return data


def youtube_trending(region="US", n=25):
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        raise RuntimeError("YOUTUBE_API_KEY is not set")
    payload = _get_json(
        "https://www.googleapis.com/youtube/v3/videos",
        params={"part": "snippet,statistics", "chart": "mostPopular",
                "regionCode": region, "maxResults": n,
                "key": key},
        headers={"User-Agent": USER_AGENT}
    )
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("Invalid YouTube response shape")
    out = []
    for i in items:
        snippet = i.get("snippet", {}) if isinstance(i, dict) else {}
        stats = i.get("statistics", {}) if isinstance(i, dict) else {}
        title = snippet.get("title")
        channel = snippet.get("channelTitle")
        if not title or not channel:
            continue
        out.append({
            "title": title,
            "channel": channel,
            "views": int(stats.get("viewCount", 0) or 0),
            "visual_hint": "high",
            "source": "youtube_trending"
        })
    return out


def hacker_news(n=15):
    base = "https://hacker-news.firebaseio.com/v0/"
    ids = _get_json(base + "topstories.json")
    if not isinstance(ids, list):
        raise ValueError("Invalid Hacker News topstories response")
    titles = []
    for i in ids[:n]:
        try:
            item = _get_json(base + "item/%s.json" % i)
        except Exception:
            continue
        if isinstance(item, dict):
            title = item.get("title") or ""
            if title:
                titles.append(title)
    return titles


def wikipedia_top(lang="en", n=25):
    d = datetime.date.today() - datetime.timedelta(days=2)
    url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/top/"
           "%s.wikipedia/all-access/%s" % (lang, d.strftime("%Y/%m/%d")))
    payload = _get_json(url, headers={"User-Agent": USER_AGENT})
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("Invalid Wikipedia response shape")
    articles = items[0].get("articles") if isinstance(items[0], dict) else None
    if not isinstance(articles, list):
        raise ValueError("Invalid Wikipedia articles response")
    out = []
    for a in articles[:n]:
        if isinstance(a, dict) and a.get("article"):
            out.append(a["article"].replace("_", " "))
    return out


def collect():
    sources = [("youtube_trending", youtube_trending),
               ("hacker_news", hacker_news),
               ("wikipedia_top", wikipedia_top)]
    data = {"_meta": {"fetched_at": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")}}
    for name, fn in sources:
        try:
            result = fn()
            if not isinstance(result, list):
                raise ValueError("source did not return a list")
            data[name] = result
            data["_meta"][name] = {"ok": True, "count": len(result)}
        except Exception as e:
            print("Source failed:", name, str(e)[:200])
            data[name] = []
            data["_meta"][name] = {"ok": False, "error": str(e)[:200]}
    return data
