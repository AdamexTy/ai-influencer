import json
import datetime
import pathlib
from market import collect
from agent import decide
from guardrails import check
from produce import make_video
from upload import upload
from feedback import update_metrics

MEM = pathlib.Path("memory/memory.json")

def load():
    if MEM.exists():
        return json.loads(MEM.read_text(encoding="utf-8"))
    return {"channel": {}, "videos": [], "lessons": []}

def save(mem):
    MEM.parent.mkdir(exist_ok=True)
    MEM.write_text(json.dumps(mem, ensure_ascii=False, indent=2), encoding="utf-8")

def main():
    mem = load()
    update_metrics(mem)
    market = collect()

    plan = None
    for attempt in range(3):              # fino a 3 tentativi se il piano viene scartato
        try:
            candidate = decide(market, mem)
        except Exception as e:
            print("Errore nel contattare Gemini:", e)
            mem["lessons"].append("Tentativo fallito per errore tecnico: %s" % str(e)[:200])
            continue
        ok, why = check(candidate, mem)
        if ok:
            plan = candidate
            break
        mem["lessons"].append("Piano scartato (%s): %s" % (candidate.get("topic"), why))

    if plan is None:
        print("Nessun piano valido oggi.")
        save(mem)
        return

    path = make_video(plan)
    vid = upload(path, plan)
    mem["videos"].append({
        "id": vid, "date": datetime.date.today().isoformat(),
        "niche": plan["niche"], "topic": plan["topic"], "title": plan["title"],
        "rationale": plan.get("rationale", ""), "views": 0, "likes": 0, "comments": 0})
    save(mem)
    print("Pubblicato:", "https://youtube.com/shorts/" + vid)

if __name__ == "__main__":
    main()
