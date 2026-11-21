"""Upload a captioned Short to starGaming through the YouTube Data API (no browser, no file picker).

python yt_upload.py auth       one-time Google sign-in; saves token.json next to this script
python yt_upload.py check      read-only test: channel name + latest uploads
python yt_upload.py upload <clip.mp4> "<title>" "<scene line>" "<extra tags>" "<scene>"
                           [--streamer "IShowSpeed"] [--date 2026-11-19] [--privacy public] [--ai]

`upload` sends clips/<date>/captioned/<clip>_captioned.mp4 with the approved format from
log_upload.upload_texts (hashtags, scene line, subscribe line, credit), Gaming category,
not made for kids, altered/synthetic content declared with --ai (AI-made videos), then logs the row to caption_tracker.csv and uploads.csv.

Until Google approves the project's YouTube API audit, every API upload is locked to Private
and can't be made public, so keep using the browser workflow (CAPTION_WORKFLOW.md step 7) until then.
client_secret.json and token.json are secrets: never share or publish them.
"""
import argparse
import os
import subprocess
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from log_upload import upload_texts

HERE = os.path.dirname(os.path.abspath(__file__))
SECRET = os.path.join(HERE, "client_secret.json")
TOKEN = os.path.join(HERE, "token.json")
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly"]
GAMING = "20"  # YouTube category id


def credentials():
    """Saved sign-in, refreshed when needed; opens the browser sign-in when there is none (or it expired)."""
    creds = Credentials.from_authorized_user_file(TOKEN, SCOPES) if os.path.exists(TOKEN) else None
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:  # app in Testing: refresh tokens expire after 7 days -> sign in again
            creds = None
    if not creds or not creds.valid:
        if not os.path.exists(SECRET):
            sys.exit(f"missing {SECRET}: download the OAuth client JSON from Google Cloud (Clients).")
        creds = InstalledAppFlow.from_client_secrets_file(SECRET, SCOPES).run_local_server(port=0)
        with open(TOKEN, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return creds


def youtube():
    return build("youtube", "v3", credentials=credentials())


def check():
    yt = youtube()
    ch = yt.channels().list(part="snippet,contentDetails,statistics", mine=True).execute()["items"][0]
    print(f"signed in to channel: {ch['snippet']['title']} ({ch['id']}), "
          f"{ch['statistics'].get('videoCount', '?')} videos, {ch['statistics'].get('subscriberCount', '?')} subscribers")
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    items = yt.playlistItems().list(part="snippet", playlistId=uploads, maxResults=5).execute()["items"]
    for it in items:
        sn = it["snippet"]
        print(f"  {sn['publishedAt'][:10]}  {sn['resourceId']['videoId']}  {sn['title']}")


def upload(a):
    stem = os.path.splitext(a.clip)[0]
    path = os.path.join(HERE, "clips", a.date, "captioned", f"{stem}_captioned.mp4")
    if not os.path.exists(path):
        sys.exit(f"not found: {path}")
    _, _, description, tags = upload_texts(a.streamer, a.scene_line, a.extra_tags)
    body = {
        "snippet": {"title": a.title, "description": description, "categoryId": GAMING,
                    "tags": [t.strip() for t in tags.split(",") if t.strip()]},
        "status": {"privacyStatus": a.privacy, "selfDeclaredMadeForKids": False,
                   "containsSyntheticMedia": a.ai},
    }
    request = youtube().videos().insert(part="snippet,status", body=body,
                                        media_body=MediaFileUpload(path, chunksize=-1, resumable=True))
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  uploading {int(status.progress() * 100)}%")
    vid = response["id"]
    url = f"https://youtube.com/shorts/{vid}"
    print(f"uploaded {a.clip} -> {url} ({response['status']['privacyStatus']})")

    # record it the same way as the browser workflow (CAPTION_WORKFLOW.md step 8)
    py = sys.executable
    subprocess.run([py, os.path.join(HERE, "caption.py"), "uploaded", a.clip, url], cwd=HERE)
    subprocess.run([py, os.path.join(HERE, "log_upload.py"), a.clip, vid, a.title, a.scene_line, a.extra_tags,
                    a.scene, "--streamer", a.streamer, "--date", a.date, "--copyright", "Not checked (API upload)",
                    "--notes", f"uploaded via YouTube Data API ({a.privacy})"], cwd=HERE)


p = argparse.ArgumentParser(description="Upload Shorts to starGaming via the YouTube Data API")
sub = p.add_subparsers(dest="cmd", required=True)
sub.add_parser("auth", help="one-time Google sign-in")
sub.add_parser("check", help="read-only test: channel + latest uploads")
u = sub.add_parser("upload", help="upload a captioned clip and log it")
u.add_argument("clip")
u.add_argument("title")
u.add_argument("scene_line", help="the one-sentence line used in the description")
u.add_argument("extra_tags", nargs="?", default="", help="clip-specific tags, comma-separated")
u.add_argument("scene", nargs="?", default="", help="what happens in the clip (for the log)")
u.add_argument("--streamer", default="Fresh Spawns")
u.add_argument("--date", default="2026-11-19", help="clips/<date>/ folder")
u.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
u.add_argument("--ai", action="store_true", help="declare altered/synthetic (AI-generated) content")
a = p.parse_args()

if a.cmd == "auth":
    credentials()
    print(f"signed in; token saved to {TOKEN}")
elif a.cmd == "check":
    check()
else:
    upload(a)
