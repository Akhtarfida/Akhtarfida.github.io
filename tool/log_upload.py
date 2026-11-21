"""Append one published Short to uploads.csv (see CAPTION_WORKFLOW.md step 8).

python log_upload.py <clip.mp4> [video_id] ["<title>"] ["<scene line>"] ["<extra tags>"] ["<scene>"]
                     [--streamer "Fresh Spawns"] [--platform YouTube] [--url ...] [--notes "..."]

Only <clip> is required. Anything that isn't given or can't be found is left blank: the script
never stops on a missing value. The source video and the clip's start time in it are looked up
from work/run_<key>.ps1 and work/<key>.log (written when clipper.py cut the clip); pass
--source-video / --source-start to override.
"""
import argparse
import csv
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "uploads.csv")
COLS = ["clip", "platform", "uploaded_at", "url", "video_id", "channel", "title", "on_video_caption",
        "description", "hashtags", "tags", "scene", "source_streamer", "source_platform", "source_video",
        "source_start", "source_link", "credit_line", "audience", "visibility", "copyright_check",
        "captioned_file", "notes"]
URLS = {"youtube": "https://youtube.com/shorts/{}"}  # post-link pattern per platform; others need --url


def read_text(path):
    """File contents as text (handles the UTF-16 logs PowerShell's Tee-Object writes), or '' on any problem."""
    try:
        raw = open(path, "rb").read()
        if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
            return raw.decode("utf-16", "ignore")
        return raw.decode("utf-8-sig", "ignore")
    except OSError:
        return ""


def find_source(clip):
    """Return (source_video, source_start) from the clipper's run script and log; blanks when not found."""
    key = clip.split("_")[0]
    video = start = ""
    m = re.search(r"\$url\s*=\s*'([^']+)'", read_text(os.path.join(HERE, "work", f"run_{key}.ps1")))
    if m:
        video = m.group(1)
    stem, last = os.path.splitext(clip)[0], ""
    for line in read_text(os.path.join(HERE, "work", f"{key}.log")).splitlines():
        m = re.search(r"\[\d+/\d+\] (\d+:\d\d:\d\d)", line)
        if m:
            last = m.group(1)
        elif stem and stem in line and last:
            start = last
            break
    return video, start


def to_seconds(t):
    """'1:02:03' or '62:03' or '3723' -> 3723; None if it isn't a time."""
    try:
        total = 0
        for part in t.strip().split(":"):
            total = total * 60 + int(part)
        return total
    except (ValueError, AttributeError):
        return None


def source_platform(url):
    for host, name in (("youtu", "YouTube"), ("twitch", "Twitch"), ("kick", "Kick"), ("tiktok", "TikTok")):
        if host in url:
            return name
    return ""


def on_video_caption(title):
    """Title minus its hashtags and trailing emoji, e.g. 'First crash in GTA VI 💀 #gta6' -> 'First crash in GTA VI'."""
    text = title.split(" #")[0].strip()
    while text and not text[-1].isascii():
        text = text[:-1].rstrip()
    return text


def upload_texts(streamer, scene_line="", extra_tags=""):
    """The approved upload format (CAPTION_WORKFLOW.md): returns (hashtags, credit, description, tags)."""
    streamer = streamer.strip()
    handle = re.sub(r"[^a-z0-9]", "", streamer.lower())
    hashtags = " ".join(["#gta6 #gtavi #gta", f"#{handle}" if handle else "", "#gta6gameplay #shorts"]).replace("  ", " ")
    credit = f"Gameplay credit: {streamer} (original streamer). Clipped and edited by starGaming." if streamer else ""
    description = "\n\n".join(x for x in [hashtags, scene_line, "Subscribe for daily GTA 6 moments 🔔", credit] if x)
    tags = ", ".join(x for x in ["gta 6", "gta vi", streamer.lower(), handle, "gta 6 gameplay", extra_tags] if x)
    return hashtags, credit, description, tags


def main():
    p = argparse.ArgumentParser()
    p.add_argument("clip")
    p.add_argument("video_id", nargs="?", default="")
    p.add_argument("title", nargs="?", default="")
    p.add_argument("scene_line", nargs="?", default="", help="the one-sentence line used in the description")
    p.add_argument("extra_tags", nargs="?", default="", help="clip-specific tags, comma-separated")
    p.add_argument("scene", nargs="?", default="", help="what happens in the clip (for the log)")
    p.add_argument("--streamer", default="Fresh Spawns")
    p.add_argument("--date", default="2026-11-19", help="clips/<date>/ folder")
    p.add_argument("--copyright", default="No issues found")
    p.add_argument("--platform", default="YouTube", help="where it was uploaded: YouTube, TikTok, Instagram, ...")
    p.add_argument("--url", default="", help="post URL (built automatically for YouTube)")
    p.add_argument("--source-video", default="")
    p.add_argument("--source-start", default="", help="h:mm:ss in the source video")
    p.add_argument("--notes", default="")
    a = p.parse_args()

    streamer = a.streamer.strip()
    hashtags, credit, description, tags = upload_texts(streamer, a.scene_line, a.extra_tags)

    try:
        src_video, src_start = find_source(a.clip)
    except Exception:  # a source lookup problem must never block logging the upload
        src_video, src_start = "", ""
    src_video, src_start = a.source_video or src_video, a.source_start or src_start
    secs = to_seconds(src_start) if src_start else None
    if secs is None:
        src_start = ""  # not a valid time: leave it blank
    src_link = f"{src_video}{'&' if '?' in src_video else '?'}t={secs}s" if src_video and secs is not None else src_video

    url = a.url
    if not url and a.video_id and URLS.get(a.platform.lower()):
        url = URLS[a.platform.lower()].format(a.video_id)

    stem = os.path.splitext(a.clip)[0]
    values = {
        "clip": a.clip, "platform": a.platform, "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "url": url, "video_id": a.video_id, "channel": "starGaming", "title": a.title,
        "on_video_caption": on_video_caption(a.title), "description": description, "hashtags": hashtags,
        "tags": tags, "scene": a.scene, "source_streamer": streamer, "source_platform": source_platform(src_video),
        "source_video": src_video, "source_start": src_start, "source_link": src_link, "credit_line": credit,
        "audience": "Not made for kids", "visibility": "Public", "copyright_check": a.copyright,
        "captioned_file": os.path.join("clips", a.date, "captioned", f"{stem}_captioned.mp4") if stem else "",
        "notes": a.notes,
    }

    # Follow the header already in the file, so added/reordered columns keep working; unknown columns stay blank.
    header = COLS
    if os.path.exists(CSV):
        first = read_text(CSV).splitlines()[:1]
        if first:
            header = next(csv.reader(first))
    try:
        new = not os.path.exists(CSV) or os.path.getsize(CSV) == 0
        with open(CSV, "a", newline="", encoding="utf-8-sig" if new else "utf-8") as f:
            w = csv.DictWriter(f, header, restval="", extrasaction="ignore")
            if new:
                w.writeheader()
            w.writerow(values)
    except PermissionError:
        sys.exit(f"could not write {CSV}: it is open in another program (Excel?). Close it and run again.")

    blank = [c for c in header if not str(values.get(c, "")).strip()]
    print(f"logged {a.clip} [{a.platform}] -> {url or '(no url)'}")
    print(f"  source: {src_start or '?'} in {src_video or '?'}")
    if blank:
        print(f"  left blank: {', '.join(blank)}")


if __name__ == "__main__":
    main()
