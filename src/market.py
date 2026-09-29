import os
import datetime
import requests

def youtube_trending(region="IT", n=25):
    r = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={"part": "snippet,statistics", "chart": "mostPopular",
                "regionCode": region, "maxResults": n,
                "key": os.environ["YOUTUBE_API_KEY"]},
        timeout=30)
    r.raise_for_status()
    out = []
    for i in r.json().get("items", []):
        out.append({"title": i["snippet"]["title"],
                    "channel": i["snippet"]["channelTitle"],
                    "views": int(i["statistics"].get("viewCount", 0))})
    return out

def hacker_news(n=15):
    base = "https://hacker-news.firebaseio.com/v0/"
    ids = requests.get(base + "topstories.json", timeout=30).json()[:n]
    titles = []
    for i in ids:
        item = requests.get(base + "item/%s.json" % i, timeout=30).json()
        titles.append(item.get("title", ""))
    return titles

def wikipedia_top(lang="it", n=25):
    d = datetime.date.today() - datetime.timedelta(days=2)
    url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/top/"
           "%s.wikipedia/all-access/%s" % (lang, d.strftime("%Y/%m/%d")))
    r = requests.get(url, headers={"User-Agent": "ai-experiment/1.0"}, timeout=30)
    arts = r.json()["items"][0]["articles"][:n]
    return [a["article"].replace("_", " ") for a in arts]

def collect():
    sources = [("youtube_trending", youtube_trending),
               ("hacker_news", hacker_news),
               ("wikipedia_top", wikipedia_top)]
    data = {}
    for name, fn in sources:
        try:
            data[name] = fn()
        except Exception as e:
            print("Fonte fallita:", name, e)
            data[name] = []
    return data
