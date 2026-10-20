import math
import os
import shutil
import subprocess
import sys
import time

import requests

WORK = "work"
VOICE = "en_US-lessac-medium"   # Piper, gratuito e offline. Alternative: en_US-amy-medium, en_GB-alba-medium
VOICES = "voices"
W, H = 720, 1280
MIN_DISTINCT_CLIPS = 3


def sh(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        print("Command failed:", " ".join(cmd))
        print((p.stderr or "")[-2000:])
        raise subprocess.CalledProcessError(p.returncode, cmd)


def duration(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                   "format=duration", "-of", "csv=p=0", path])
    return float(out.strip())


def _cleanup_old_runs():
    os.makedirs(WORK, exist_ok=True)
    run_dirs = []
    for name in os.listdir(WORK):
        p = os.path.join(WORK, name)
        if name.startswith("run-") and os.path.isdir(p):
            run_dirs.append(p)
    run_dirs.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    for stale in run_dirs[5:]:
        shutil.rmtree(stale, ignore_errors=True)


def _new_run_dir():
    _cleanup_old_runs()
    run_dir = os.path.join(WORK, "run-%s" % time.strftime("%Y%m%d-%H%M%S"))
    idx = 0
    while os.path.exists(run_dir):
        idx += 1
        run_dir = os.path.join(WORK, "run-%s-%d" % (time.strftime("%Y%m%d-%H%M%S"), idx))
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def make_voice(text, path):
    model = os.path.join(VOICES, VOICE + ".onnx")
    if not os.path.exists(model):
        sh([sys.executable, "-m", "piper.download_voices", VOICE, "--download-dir", VOICES])
    p = subprocess.run([sys.executable, "-m", "piper", "-m", model, "-f", path],
                       input=text.encode("utf-8"),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        print("Piper failed:", (p.stderr or b"").decode("utf-8", "ignore")[-2000:])
        raise subprocess.CalledProcessError(p.returncode, "piper")
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise RuntimeError("Voice synthesis produced no audio")


def _query_terms(keywords, topic):
    terms = []
    for kw in keywords:
        kw = str(kw).strip()
        if kw:
            terms.append(kw)
    if topic:
        terms.append(str(topic).strip())
        terms.extend([w for w in str(topic).split() if len(w) > 4])
    seen = set()
    deduped = []
    for t in terms:
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(t)
    return deduped


def fetch_clips(keywords, need, run_dir, topic=""):
    headers = {"Authorization": os.environ["PEXELS_API_KEY"]}
    urls, seen = [], set()
    for kw in _query_terms(keywords, topic):
        try:
            r = requests.get("https://api.pexels.com/videos/search", headers=headers, timeout=30,
                             params={"query": kw, "orientation": "portrait",
                                     "size": "medium", "per_page": 8})
        except requests.RequestException as e:
            print("Clip search failed for %r: %s" % (kw, e))
            continue
        if r.status_code != 200:
            print("Clip search returned HTTP %s for %r" % (r.status_code, kw))
            continue
        data = r.json()
        if not isinstance(data, dict):
            continue
        for v in data.get("videos", []):
            vid = v.get("id")
            if vid in seen:
                continue
            files = sorted(v.get("video_files", []), key=lambda f: abs(f.get("width", 0) - W))
            if files and files[0].get("link"):
                urls.append(files[0]["link"])
                seen.add(vid)
        if len(urls) >= need * 2:
            break
    paths = []
    for u in urls:
        if len(paths) >= max(need, MIN_DISTINCT_CLIPS):
            break
        try:
            resp = requests.get(u, timeout=120)
        except requests.RequestException as e:
            print("Clip download failed: %s" % e)
            continue
        if resp.status_code != 200 or not resp.content:
            print("Skipping clip (HTTP %s, %d bytes)" % (resp.status_code, len(resp.content or b"")))
            continue
        p = os.path.join(run_dir, "raw%d.mp4" % len(paths))
        with open(p, "wb") as f:
            f.write(resp.content)
        if os.path.getsize(p) == 0:
            continue
        paths.append(p)
    return paths


def make_srt(audio, srt):
    from faster_whisper import WhisperModel
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segs, _ = model.transcribe(audio, language="en", beam_size=5, vad_filter=True)

    def ts(t):
        h, rem = divmod(t, 3600)
        m, s = divmod(rem, 60)
        return ("%02d:%02d:%06.3f" % (h, m, s)).replace(".", ",")
    with open(srt, "w", encoding="utf-8") as f:
        for n, s in enumerate(segs, 1):
            f.write("%d\n%s --> %s\n%s\n\n" % (n, ts(s.start), ts(s.end), s.text.strip()))


def _escape_sub_path(path):
    escaped = path.replace("\\", "\\\\")
    escaped = escaped.replace(":", "\\:")
    escaped = escaped.replace("'", "\\'")
    escaped = escaped.replace("[", "\\[").replace("]", "\\]")
    escaped = escaped.replace(",", "\\,")
    return escaped


def _validate_mp4(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise RuntimeError("Final MP4 is missing or empty")
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries",
        "stream=codec_type", "-of", "csv=p=0", path
    ], text=True)
    streams = {x.strip() for x in out.splitlines() if x.strip()}
    if "video" not in streams or "audio" not in streams:
        raise RuntimeError("Final MP4 is missing required audio/video streams")


def make_video(plan):
    run_dir = _new_run_dir()
    voice = os.path.join(run_dir, "voice.wav")
    make_voice(plan["script"], voice)
    dur = duration(voice)
    seg = 4.0
    need = max(3, math.ceil(dur / seg))
    clips = fetch_clips(plan["keywords"], need, run_dir, topic=plan.get("topic", ""))

    distinct_needed = min(MIN_DISTINCT_CLIPS, need)
    if len(clips) < distinct_needed:
        raise RuntimeError(
            "Insufficient distinct clips (%d found, need at least %d); try a more visual topic/keywords"
            % (len(clips), distinct_needed)
        )

    parts = []
    for i in range(need):
        src = clips[i % len(clips)]
        out = os.path.join(run_dir, "part%d.mp4" % i)
        vf = ("scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,fps=30"
              % (W, H, W, H))
        sh(["ffmpeg", "-y", "-i", src, "-t", str(seg), "-vf", vf, "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", out])
        parts.append(out)

    list_path = os.path.join(run_dir, "list.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for p in parts:
            f.write("file '%s'\n" % os.path.basename(p).replace("'", "'\\''"))

    silent = os.path.join(run_dir, "silent.mp4")
    sh(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
        "-c", "copy", silent])

    srt_path = os.path.join(run_dir, "subs.srt")
    make_srt(voice, srt_path)

    final = os.path.join(run_dir, "final.mp4")
    style = "FontName=DejaVu Sans,Bold=1,FontSize=16,Alignment=2,MarginV=180,Outline=2"
    subs_filter = "subtitles=%s:force_style='%s'" % (_escape_sub_path(srt_path), style)
    sh(["ffmpeg", "-y", "-i", silent, "-i", voice,
        "-vf", subs_filter,
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-c:a", "aac", "-b:a", "128k", "-shortest", final])

    _validate_mp4(final)
    return final
