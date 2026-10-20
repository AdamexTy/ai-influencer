import os
import re
import time

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly"]
ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"

# YouTube category: 27 = Education, 28 = Science & Technology, 20 = Gaming, 15 = Pets & Animals.
CATEGORY_ID = "27"
RETRYABLE_STATUS = {410, 500, 502, 503, 504}


def get_credentials(scopes=None):
    return Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=scopes or SCOPES)


def get_service():
    return build("youtube", "v3", credentials=get_credentials())


def _clean_text(value, max_len):
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(value or "")).strip()
    return re.sub(r"\s+", " ", text)[:max_len]


def _sanitize_tags(plan):
    raw = list(plan.get("hashtags", [])) + list(plan.get("keywords", []))
    tags = []
    seen = set()
    for item in raw:
        tag = _clean_text(str(item).replace("#", ""), 30)
        tag = re.sub(r"[^A-Za-z0-9 _-]", "", tag).strip()
        if not tag:
            continue
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        tags.append(tag)
        if len(tags) >= 15:
            break
    return tags


def _category_for_plan(plan):
    text = (str(plan.get("niche", "")) + " " + str(plan.get("topic", ""))).lower()
    if "gaming" in text:
        return "20"
    if "animal" in text or "wildlife" in text or "biology" in text or "pet" in text:
        return "15"
    if "technology" in text or "science" in text or "engineering" in text:
        return "28"
    return CATEGORY_ID


def upload(path, plan, privacy="public"):
    yt = get_service()
    title = _clean_text(plan.get("title", "Untitled"), 100)
    description = _clean_text(plan.get("description", ""), 4500)
    tags = _sanitize_tags(plan)
    hashtag_line = " ".join("#" + t.replace(" ", "") for t in tags[:5])
    desc = (description + "\n\n" + hashtag_line +
            "\n\nChannel run by an AI. Footage: Pexels.")[:5000]
    body = {
        "snippet": {"title": title, "description": desc,
                    "tags": tags, "categoryId": _category_for_plan(plan),
                    "defaultLanguage": "en", "defaultAudioLanguage": "en"},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False,
                   "containsSyntheticMedia": True}}
    for attempt in range(3):
        try:
            media = MediaFileUpload(path, mimetype="video/mp4", resumable=True,
                                    chunksize=5 * 1024 * 1024)
            req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
            resp = None
            while resp is None:
                _, resp = req.next_chunk()
            return resp["id"]
        except HttpError as e:
            status = getattr(e.resp, "status", None)
            if status in RETRYABLE_STATUS and attempt < 2:
                print("Upload retryable HTTP %s, retrying (%d/3)..." % (status, attempt + 2))
                time.sleep(10 * (attempt + 1))
                continue
            if status in RETRYABLE_STATUS:
                print("Upload failed after retries (HTTP %s)." % status)
            else:
                print("Upload failed with non-retryable HTTP status: %s" % status)
            raise
