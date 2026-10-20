import math
import re
from difflib import SequenceMatcher

BLOCKED = ["vaccin", "cure for", "diagnos", "invest in", "cryptocurrenc", "gambl",
           "election", "political party", "porn", "suicid", "weapon", "drug",
           "conspiracy"]

# Kept close to the 70-120 words the prompt asks for, with a small margin so
# a reasonable script is never rejected (which would waste an attempt).
MIN_WORDS = 55
MAX_WORDS = 150
MIN_TITLE_LEN = 8
MAX_TITLE_LEN = 90
MIN_KEYWORDS = 3
MAX_KEYWORDS = 12
MAX_HASHTAGS = 8


def _norm(text):
    """Normalise text for duplicate comparison: lowercase, letters and
    digits only (so 'Hello, World!' == 'hello world')."""
    return "".join(c for c in (text or "").lower() if c.isalnum())


def _tokens(text):
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2}


def _jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a | b))


def _looks_like_english(text):
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    ascii_letters = sum(1 for c in letters if ord(c) < 128)
    return ascii_letters / float(len(letters)) >= 0.85


def _is_string_list(value, min_items=0, max_items=math.inf):
    if not isinstance(value, list):
        return False
    cleaned = [x for x in value if isinstance(x, str) and x.strip()]
    return min_items <= len(cleaned) <= max_items


def _validate_shape(plan):
    if not isinstance(plan, dict):
        return False, "plan is not a JSON object"

    required = ["niche", "topic", "title", "script", "keywords", "description", "hashtags"]
    for field in required:
        if field not in plan:
            return False, "missing required field: %s" % field

    if not isinstance(plan.get("niche"), str) or not plan["niche"].strip():
        return False, "invalid niche"
    if not isinstance(plan.get("topic"), str) or not plan["topic"].strip():
        return False, "invalid topic"
    if not isinstance(plan.get("title"), str):
        return False, "invalid title"
    if not isinstance(plan.get("script"), str):
        return False, "invalid script"
    if not isinstance(plan.get("description"), str) or not plan["description"].strip():
        return False, "invalid description"
    if not _is_string_list(plan.get("keywords"), MIN_KEYWORDS, MAX_KEYWORDS):
        return False, "keywords must be a list of %d-%d strings" % (MIN_KEYWORDS, MAX_KEYWORDS)
    if not _is_string_list(plan.get("hashtags"), 0, MAX_HASHTAGS):
        return False, "hashtags must be a list of up to %d strings" % MAX_HASHTAGS

    title_len = len(plan["title"].strip())
    if title_len < MIN_TITLE_LEN or title_len > MAX_TITLE_LEN:
        return False, "invalid title length (%d chars)" % title_len

    script = plan["script"].strip()
    words = len(script.split())
    if words < MIN_WORDS or words > MAX_WORDS:
        return False, "invalid script length (%d words)" % words
    if not _looks_like_english(script):
        return False, "script is not in expected English format"
    return True, ""


def _is_near_duplicate(plan, old_video):
    new_title_tokens = _tokens(plan.get("title", ""))
    old_title_tokens = _tokens(old_video.get("title", ""))
    shared_title_tokens = len(new_title_tokens & old_title_tokens)
    min_title_tokens = min(len(new_title_tokens) or 1, len(old_title_tokens) or 1)

    title_tokens = _jaccard(new_title_tokens, old_title_tokens)
    topic_sim = _jaccard(_tokens(plan.get("topic", "")), _tokens(old_video.get("topic", "")))
    title_ratio = SequenceMatcher(None, _norm(plan.get("title", "")), _norm(old_video.get("title", ""))).ratio()

    if shared_title_tokens >= 4 and (shared_title_tokens / float(min_title_tokens)) >= 0.66:
        return True
    return title_tokens >= 0.75 or title_ratio >= 0.78 or topic_sim >= 0.80


def check(plan, mem):
    ok, why = _validate_shape(plan)
    if not ok:
        return False, why

    text = (plan.get("title", "") + " " + plan.get("script", "") + " " + plan.get("topic", "")).lower()
    for w in BLOCKED:
        if w in text:
            return False, "blocked word: " + w

    new_title = _norm(plan.get("title", ""))
    new_topic = _norm(plan.get("topic", ""))

    for v in mem.get("videos", []):
        old_title = _norm(v.get("title", ""))
        old_topic = _norm(v.get("topic", ""))
        if new_title and old_title and new_title == old_title:
            return False, "duplicate title"
        if new_topic and old_topic and new_topic == old_topic:
            return False, "duplicate topic"
        if _is_near_duplicate(plan, v):
            return False, "near-duplicate topic/title"
    return True, ""
