import os
import math
import sys
import subprocess
import requests

WORK = "work"
VOICE = "en_US-lessac-medium"   # Piper, gratuito e offline. Alternative: en_US-amy-medium, en_GB-alba-medium
VOICES = "voices"
W, H = 720, 1280


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


def fetch_clips(keywords, need):
    headers = {"Authorization": os.environ["PEXELS_API_KEY"]}
    urls, seen = [], set()
    for kw in keywords:
        try:
            r = requests.get("https://api.pexels.com/videos/search", headers=headers, timeout=30,
                             params={"query": kw, "orientation": "portrait",
                                     "size": "medium", "per_page": 5})
        except requests.RequestException as e:
            print("Clip search failed for %r: %s" % (kw, e))
            continue
        if r.status_code != 200:
            print("Clip search returned HTTP %s for %r" % (r.status_code, kw))
            continue
        for v in r.json().get("videos", []):
            vid = v.get("id")
            if vid in seen:
                continue
            files = sorted(v.get("video_files", []), key=lambda f: abs(f.get("width", 0) - W))
            if files:
                urls.append(files[0]["link"])
                seen.add(vid)
        if len(urls) >= need:
            break
    paths = []
    for u in urls:
        if len(paths) >= need:
            break
        try:
            resp = requests.get(u, timeout=120)
        except requests.RequestException as e:
            print("Clip download failed: %s" % e)
            continue
        if resp.status_code != 200 or not resp.content:
            print("Skipping clip (HTTP %s, %d bytes)" % (resp.status_code, len(resp.content or b"")))
            continue
        p = os.path.join(WORK, "raw%d.mp4" % len(paths))
        with open(p, "wb") as f:
            f.write(resp.content)
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


def make_video(plan):
    os.makedirs(WORK, exist_ok=True)
    voice = os.path.join(WORK, "voice.wav")
    make_voice(plan["script"], voice)
    dur = duration(voice)
    seg = 4.0
    need = max(3, math.ceil(dur / seg))
    clips = fetch_clips(plan["keywords"], need)
    if not clips:
        raise RuntimeError("No stock clips found")
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
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-c:a", "aac", "-b:a", "128k", "-shortest", final])
    return final
