import datetime
import json
import pathlib

from market import collect
from agent import decide
from guardrails import check
from produce import make_video
from upload import upload
from feedback import update_metrics

MEM = pathlib.Path("memory/memory.json")


def _default_memory():
    return {"channel": {}, "videos": [], "lessons": []}


def _normalize_memory(mem):
    if not isinstance(mem, dict):
        mem = {}
    channel = mem.get("channel") if isinstance(mem.get("channel"), dict) else {}
    videos = mem.get("videos") if isinstance(mem.get("videos"), list) else []
    lessons = mem.get("lessons") if isinstance(mem.get("lessons"), list) else []
    normalized_videos = [v for v in videos if isinstance(v, dict)]
    normalized_lessons = [str(x) for x in lessons if x is not None]
    return {"channel": channel, "videos": normalized_videos, "lessons": normalized_lessons}


def _write_atomic(path, content):
    path.parent.mkdir(exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _backup_corrupt_file(path):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(path.name + ".corrupt-" + stamp + ".bak")
    backup.write_bytes(path.read_bytes())
    return backup


def load():
    if not MEM.exists():
        return _default_memory()

    raw = MEM.read_text(encoding="utf-8")
    parsed = None
    malformed = False
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        malformed = True
        try:
            decoder = json.JSONDecoder()
            parsed, _ = decoder.raw_decode(raw.lstrip())
        except Exception:
            parsed = _default_memory()

    mem = _normalize_memory(parsed)
    if malformed:
        backup = _backup_corrupt_file(MEM)
        print("Recovered malformed memory file; backup saved to", backup)
        _write_atomic(MEM, json.dumps(mem, ensure_ascii=False, indent=2))
    return mem


def save(mem):
    normalized = _normalize_memory(mem)
    _write_atomic(MEM, json.dumps(normalized, ensure_ascii=False, indent=2))


def main():
    mem = load()
    try:
        update_metrics(mem)
    except Exception as e:
        print("Metrics update failed (continuing anyway):", e)
    market = collect()

    plan = None
    for attempt in range(3):              # up to 3 tries if the plan gets rejected
        try:
            candidate = decide(market, mem)
        except Exception as e:
            print("Error contacting Gemini:", e)
            mem["lessons"].append("Attempt failed with a technical error: %s" % str(e)[:200])
            continue
        ok, why = check(candidate, mem)
        if ok:
            plan = candidate
            break
        topic = candidate.get("topic", "unknown") if isinstance(candidate, dict) else "unknown"
        mem["lessons"].append("Plan rejected (%s): %s" % (topic, why))

    if plan is None:
        print("No valid plan today.")
        save(mem)
        return

    try:
        path = make_video(plan)
        vid = upload(path, plan)
    except Exception as e:
        mem["lessons"].append("Production/upload failed: %s" % str(e)[:200])
        save(mem)
        raise

    mem["videos"].append({
        "id": vid, "date": datetime.date.today().isoformat(),
        "niche": plan["niche"], "topic": plan["topic"], "title": plan["title"],
        "rationale": plan.get("rationale", ""), "views": 0, "likes": 0, "comments": 0,
        "source": plan.get("source", "")
    })
    save(mem)
    print("Published:", "https://youtube.com/shorts/" + vid)


if __name__ == "__main__":
    main()
