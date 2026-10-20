import datetime

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from upload import ANALYTICS_SCOPE, SCOPES, get_credentials, get_service


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_int(value):
    try:
        return int(value)
    except Exception:
        return 0


def _safe_float(value):
    try:
        return float(value)
    except Exception:
        return 0.0


def _analytics_service():
    scopes = list(dict.fromkeys(list(SCOPES) + [ANALYTICS_SCOPE]))
    creds = get_credentials(scopes=scopes)
    return build("youtubeAnalytics", "v2", credentials=creds)


def _query_analytics(ya, video_ids, start_date, end_date, metrics):
    filters = "video==" + ",".join(video_ids)
    resp = ya.reports().query(
        ids="channel==MINE",
        startDate=start_date,
        endDate=end_date,
        dimensions="video",
        metrics=metrics,
        filters=filters,
        maxResults=200
    ).execute()
    headers = [h["name"] for h in resp.get("columnHeaders", [])]
    rows = {}
    for row in resp.get("rows", []):
        entry = dict(zip(headers, row))
        vid = entry.get("video")
        if vid:
            rows[vid] = entry
    return rows


def _append_history(video, snapshot):
    history = video.get("metrics_history")
    if not isinstance(history, list):
        history = []
    history.append(snapshot)
    video["metrics_history"] = history[-60:]


def update_metrics(mem):
    vids = mem.get("videos", [])
    ids = [v.get("id") for v in vids[-50:] if v.get("id")]
    if not ids:
        return

    ts = _now_iso()
    yt = get_service()

    stats = {}
    for i in range(0, len(ids), 50):
        r = yt.videos().list(part="statistics", id=",".join(ids[i:i + 50])).execute()
        for it in r.get("items", []):
            stats[it["id"]] = it.get("statistics", {})

    analytics = {}
    analytics_available = False
    start_date = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    end_date = datetime.date.today().isoformat()
    try:
        ya = _analytics_service()
        primary_metrics = (
            "views,likes,comments,subscribersGained,averageViewDuration,"
            "averageViewPercentage,impressions,impressionsCtr"
        )
        try:
            analytics = _query_analytics(ya, ids, start_date, end_date, primary_metrics)
        except HttpError as e:
            if getattr(e.resp, "status", None) == 400:
                fallback_metrics = (
                    "views,likes,comments,subscribersGained,averageViewDuration,averageViewPercentage"
                )
                analytics = _query_analytics(ya, ids, start_date, end_date, fallback_metrics)
            else:
                raise
        analytics_available = True
    except Exception as e:
        print("YouTube Analytics unavailable; continuing with Data API only:", str(e)[:180])

    for v in vids:
        vid = v.get("id")
        if not vid:
            continue
        s = stats.get(vid)
        if s:
            v["views"] = _safe_int(s.get("viewCount", 0))
            v["likes"] = _safe_int(s.get("likeCount", 0))
            v["comments"] = _safe_int(s.get("commentCount", 0))
        a = analytics.get(vid)
        if a:
            if "averageViewDuration" in a:
                v["avg_view_duration_seconds"] = _safe_float(a.get("averageViewDuration", 0))
            if "averageViewPercentage" in a:
                v["avg_percentage_viewed"] = _safe_float(a.get("averageViewPercentage", 0))
            if "subscribersGained" in a:
                v["subscribers_gained"] = _safe_int(a.get("subscribersGained", 0))
            if "impressions" in a:
                v["impressions"] = _safe_int(a.get("impressions", 0))
            if "impressionsCtr" in a:
                v["impressions_ctr"] = _safe_float(a.get("impressionsCtr", 0))
        snapshot = {
            "timestamp": ts,
            "views": v.get("views", 0),
            "likes": v.get("likes", 0),
            "comments": v.get("comments", 0)
        }
        if a:
            for key in ("avg_view_duration_seconds", "avg_percentage_viewed", "subscribers_gained", "impressions", "impressions_ctr"):
                if key in v:
                    snapshot[key] = v[key]
        _append_history(v, snapshot)
        v["metrics_updated_at"] = ts

    ch = yt.channels().list(part="statistics", mine=True).execute()
    if ch.get("items"):
        cs = ch["items"][0]["statistics"]
        mem.setdefault("channel", {})
        mem["channel"]["subscribers"] = _safe_int(cs.get("subscriberCount", 0))
        mem["channel"]["total_views"] = _safe_int(cs.get("viewCount", 0))
        mem["channel"]["metrics_updated_at"] = ts
        mem["channel"]["analytics_enabled"] = analytics_available
