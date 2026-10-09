import os
import time
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly"]

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
    tags = [h.replace("#", "") for h in plan.get("hashtags", [])]
    desc = plan["description"] + "\n\n" + " ".join("#" + t for t in tags) + \
        "\n\nCanale gestito da un'intelligenza artificiale. Clip: Pexels."
    body = {
        "snippet": {"title": plan["title"][:100], "description": desc,
                    "tags": tags, "categoryId": "22", "defaultLanguage": "en"},
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
