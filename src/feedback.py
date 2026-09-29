from upload import get_service

def update_metrics(mem):
    vids = mem.get("videos", [])
    ids = [v["id"] for v in vids[-50:]]
    if not ids:
        return
    yt = get_service()
    stats = {}
    for i in range(0, len(ids), 50):
        r = yt.videos().list(part="statistics", id=",".join(ids[i:i + 50])).execute()
        for it in r.get("items", []):
            stats[it["id"]] = it["statistics"]
    for v in vids:
        s = stats.get(v["id"])
        if s:
            v["views"] = int(s.get("viewCount", 0))
            v["likes"] = int(s.get("likeCount", 0))
            v["comments"] = int(s.get("commentCount", 0))
    ch = yt.channels().list(part="statistics", mine=True).execute()
    if ch.get("items"):
        cs = ch["items"][0]["statistics"]
        mem["channel"]["subscribers"] = int(cs.get("subscriberCount", 0))
        mem["channel"]["total_views"] = int(cs.get("viewCount", 0))
