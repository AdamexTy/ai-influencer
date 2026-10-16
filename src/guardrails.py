BLOCKED = ["vaccin", "cure for", "diagnos", "invest in", "cryptocurrenc", "gambl",
           "election", "political party", "porn", "suicid", "weapon", "drug",
           "conspiracy"]

# Kept close to the 70-120 words the prompt asks for, with a small margin so
# a reasonable script is never rejected (which would waste an attempt).
MIN_WORDS = 55
MAX_WORDS = 150


def _norm(title):
    """Normalise a title for duplicate comparison: lowercase, letters and
    digits only (so 'Hello, World!' == 'hello world')."""
    return "".join(c for c in (title or "").lower() if c.isalnum())


def check(plan, mem):
    text = (plan.get("title", "") + " " + plan.get("script", "")).lower()
    for w in BLOCKED:
        if w in text:
            return False, "blocked word: " + w
    words = len(plan.get("script", "").split())
    if words < MIN_WORDS or words > MAX_WORDS:
        return False, "invalid script length (%d words)" % words
    if len(plan.get("keywords", [])) < 3:
        return False, "not enough keywords"
    new_title = _norm(plan.get("title", ""))
    old = [_norm(v.get("title", "")) for v in mem.get("videos", [])]
    if new_title and new_title in old:
        return False, "duplicate title"
    return True, ""
