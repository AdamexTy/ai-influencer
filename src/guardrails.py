BLOCKED = ["vaccin", "cure for", "diagnos", "invest in", "cryptocurrenc", "gambl",
           "election", "political party", "porn", "suicid", "weapon", "drug",
           "conspiracy"]

def check(plan, mem):
    text = (plan.get("title", "") + " " + plan.get("script", "")).lower()
    for w in BLOCKED:
        if w in text:
            return False, "blocked word: " + w
    words = len(plan.get("script", "").split())
    if words < 50 or words > 160:
        return False, "invalid script length (%d words)" % words
    if len(plan.get("keywords", [])) < 3:
        return False, "not enough keywords"
    old = [v["title"].lower() for v in mem.get("videos", [])]
    if plan.get("title", "").lower() in old:
        return False, "duplicate title"
    return True, ""
