import os
import math
import asyncio
import subprocess
import requests
import edge_tts
from faster_whisper import WhisperModel

WORK = "work"
VOICE = "en-US-JennyNeural"      # femminile, tono caldo, molto usata e naturale
# VOICE = "en-GB-SoniaNeural"    # britannica, molto chiara
# VOICE = "en-US-GuyNeural"      # maschile
W, H = 720, 1280

def sh(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def duration(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                   "format=duration", "-of", "csv=p=0", path])
    return float(out.strip())

def make_voice(text, path):
    async def go():
        await edge_tts.Communicate(text, VOICE).save(path)
    asyncio.run(go())

def fetch_clips(keywords, need):
    headers = {"Authorization": os.environ["PEXELS_API_KEY"]}
    urls = []
    for kw in keywords:
        r = requests.get("https://api.pexels.com/videos/search", headers=headers, timeout=30,
                         params={"query": kw, "orientation": "portrait", "per_page": 3})
        if r.status_code != 200:
            continue
        for v in r.json().get("videos", []):
            files = sorted(v["video_files"], key=lambda f: abs(f.get("width", 0) - W))
            if files:
                urls.append(files[0]["link"])
        if len(urls) >= need:
            break
    paths = []
    for i, u in enumerate(urls[:need]):
        p = os.path.join(WORK, "raw%d.mp4" % i)
        with open(p, "wb") as f:
            f.write(requests.get(u, timeout=120).content)
        paths.append(p)
    return paths

def make_srt(audio, srt):
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segs, _ = model.transcribe(audio, language="en", beam_size=5, vad_filter=True)
    def ts(t):
        h, rem = divmod(t, 3600)
        m, s = divmod(rem, 60)
        return ("%02d:%02d:%06.3f" % (h, m, s)).replace(".", ",")
    with open(srt, "w", encoding="utf-8") as f:
        for n, s in enumerate(segs, 1):
            f.write("%d\n%s --> %s\n%s\n\n" % (n, ts(s.start), ts(s.end), s.text.strip()))

def make_video(plan):
    os.makedirs(WORK, exist_ok=True)
    voice = os.path.join(WORK, "voice.mp3")
    make_voice(plan["script"], voice)
    dur = duration(voice)
    seg = 4.0
    need = max(3, math.ceil(dur / seg))
    clips = fetch_clips(plan["keywords"], need)
    if not clips:
        raise RuntimeError("Nessuna clip trovata")
    parts = []
    for i in range(need):
        src = clips[i % len(clips)]
        out = os.path.join(WORK, "part%d.mp4" % i)
        vf = ("scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,fps=30"
              % (W, H, W, H))
        sh(["ffmpeg", "-y", "-i", src, "-t", str(seg), "-vf", vf, "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", out])
        parts.append(out)
    with open(os.path.join(WORK, "list.txt"), "w") as f:
        for p in parts:
            f.write("file '%s'\n" % os.path.basename(p))
    sh(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", os.path.join(WORK, "list.txt"),
        "-c", "copy", os.path.join(WORK, "silent.mp4")])
    make_srt(voice, os.path.join(WORK, "subs.srt"))
    final = os.path.join(WORK, "final.mp4")
    style = "FontName=DejaVu Sans,Bold=1,FontSize=16,Alignment=2,MarginV=180,Outline=2"
    sh(["ffmpeg", "-y", "-i", os.path.join(WORK, "silent.mp4"), "-i", voice,
        "-vf", "subtitles=%s/subs.srt:force_style='%s'" % (WORK, style),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-c:a", "aac", "-b:a", "128k", "-shortest", final])
    return final
