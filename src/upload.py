import os
import time
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly"]

# YouTube category: 27 = Education, 28 = Science & Technology, 20 = Gaming.
CATEGORY_ID = "27"
MAX_DESC_LEN = 5000


def _clean_text(value):
    return " ".join(str(value or "").split()).strip()


def _safe_title(plan):
    return (_clean_text(plan.get("title"))
            or _clean_text(plan.get("topic"))
            or "Daily AI Short")[:100]


def _safe_description(plan, tags):
    base = (_clean_text(plan.get("description"))
            or _clean_text(plan.get("script"))
            or "AI-generated educational short.")
    lines = [base]
    if tags:
        lines.append(" ".join("#" + t for t in tags))
    lines.append("Channel run by an AI. Footage: Pexels.")
    return "\n\n".join(lines)[:MAX_DESC_LEN]


def _clean_tags(plan):
    raw = []
    raw.extend(plan.get("hashtags", []))
    raw.extend(plan.get("keywords", []))
    tags = []
    seen = set()
    for tag in raw:
        cleaned = _clean_text(tag).lstrip("#").replace(" ", "")
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        tags.append(cleaned[:30])
        if len(tags) >= 20:
            break
    return tags

def get_service():
    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=SCOPES)
    return build("youtube", "v3", credentials=creds)

def upload(path, plan, privacy="public"):
    yt = get_service()
    tags = _clean_tags(plan)
    desc = _safe_description(plan, tags)
    title = _safe_title(plan)
    body = {
        "snippet": {"title": title, "description": desc,
                    "tags": tags, "categoryId": CATEGORY_ID,
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
            if e.resp.status in (410, 500, 502, 503, 504) and attempt < 2:
                print("Upload failed (%s), restarting (%d/3)..." % (e.resp.status, attempt + 2))
                time.sleep(10 * (attempt + 1))
            else:
                raise
