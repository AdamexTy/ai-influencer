import json
import os
import time

from google import genai

_client = None

# Preference order: the first model usually has the highest free daily
# quota. If a model runs out of quota or doesn't respond, the code
# automatically falls back to the next one. If these names become
# outdated, check https://ai.google.dev/gemini-api/docs/models
MODELS = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash"]

RULES = (
    "You are the autonomous agent running a YouTube Shorts channel in English, "
    "targeting a global audience. Your goal is to grow the channel "
    "(views, retention, subscribers) fully autonomously and honestly. "
    "You decide the niche, topic and style. "
    "RULES: (1) use the market data and the memory of past results. "
    "(2) Before choosing, look at which past videos got the most views/likes "
    "and do more of what actually worked, avoiding what flopped. "
    "(3) About 70% of the time stick to niches/formats that performed well, "
    "30% experiment with something new; if the recent videos are all in the "
    "same niche and nothing is clearly winning, you MUST explore a different "
    "niche or format this time. "
    "(4) Never repeat topics or titles already published. "
    "(5) Only true, verifiable, useful or entertaining content; forbidden: "
    "misinformation, medical/financial/legal advice, partisan politics, "
    "defamation of real people, hate speech, adult content. "
    "(6) Spoken script 25-45 seconds long (70-120 words), with a hook in the "
    "first 2 seconds and a short call to action at the end (e.g. an invitation "
    "to follow for more). "
    "(7) Never attribute invented quotes to real people. "
    "(8) Write the script entirely in English, since it will be read aloud by "
    "an English voice. "
    "(9) Stay coherent with the channel identity given below. "
    "(10) Prefer visual concepts that historically performed: practical engineering, "
    "animal intelligence/biology, hidden technology, and concrete natural phenomena. "
    "Keep a small exploration slice for adjacent ideas."
)

FORMAT = (
    "Reply ONLY with JSON with these keys: "
    "niche, topic, title (max 70 characters), script (spoken text, in English), "
    "keywords (list of 5-8 English keywords for stock footage search), "
    "description, hashtags (list, max 5), rationale (why you chose this), "
    "source (optional short factual reference: publication, institution, or URL domain)."
)


def _client_instance():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def _parse_json_response(text):
    if not text or not str(text).strip():
        raise ValueError("Gemini returned an empty response")
    raw = str(text).strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        fenced = ""
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                fenced = p[4:].strip()
                break
            if p.startswith("{") and p.endswith("}"):
                fenced = p
                break
        raw = fenced or raw
    return json.loads(raw)


def _ask(prompt):
    """Calls Gemini: tries models in order. Falls back to the next model on a
    daily-quota error OR on any other error (wrong model name, malformed
    output, ...), so a single bad model can never abort the whole chain.
    Only retries the same model with backoff when the server is temporarily
    overloaded."""
    last_error = None
    client = _client_instance()
    for model in MODELS:
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={"response_mime_type": "application/json"}
                )
                return _parse_json_response(getattr(resp, "text", ""))
            except Exception as e:
                last_error = e
                error_str = str(e)
                if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str:
                    print("Quota exhausted for %s, trying the next model..." % model)
                    break  # daily quota: no point retrying the same model
                elif "503" in error_str or "UNAVAILABLE" in error_str:
                    wait_time = 5 * (attempt + 1)
                    print("%s busy, retrying in %ss... (attempt %d/3)"
                          % (model, wait_time, attempt + 1))
                    time.sleep(wait_time)
                else:
                    print("%s failed (%s), trying the next model..."
                          % (model, str(e)[:160]))
                    break
    raise last_error


def _dominant_niche(videos):
    counts = {}
    for v in videos:
        n = (v.get("niche") or "").strip()
        if n:
            counts[n] = counts.get(n, 0) + 1
    return max(counts, key=counts.get) if counts else ""


def _identity(memory):
    """The channel identity handed to the model. The niche focus is derived
    from what the channel has actually been publishing, so the prompt stays
    coherent even if the stored channel record is stale or was never applied
    by hand."""
    ch = memory.get("channel", {})
    ident = {}
    for k in ("name", "handle", "tone", "language", "audience"):
        if ch.get(k):
            ident[k] = ch[k]
    focus = _dominant_niche(memory.get("videos", [])) or ch.get("niche", "")
    if focus:
        ident["current_niche_focus"] = focus
    if ch.get("niche") and focus and ch.get("niche") != focus:
        ident["niche_migration_note"] = (
            "Stored niche may be historical. Keep channel branding stable unless a human updates it manually."
        )
    return ident


def _performance_summary(videos):
    if not videos:
        return {"count": 0, "top_videos": [], "weak_videos": [], "dominant_niche": ""}

    recent = videos[-40:]
    scored = sorted(recent, key=lambda x: int(x.get("views", 0)), reverse=True)
    top = [{
        "title": v.get("title", ""),
        "topic": v.get("topic", ""),
        "niche": v.get("niche", ""),
        "views": int(v.get("views", 0)),
        "likes": int(v.get("likes", 0))
    } for v in scored[:8]]
    weak = [{
        "title": v.get("title", ""),
        "topic": v.get("topic", ""),
        "niche": v.get("niche", ""),
        "views": int(v.get("views", 0))
    } for v in sorted(recent, key=lambda x: int(x.get("views", 0)))[:5]]
    return {
        "count": len(videos),
        "dominant_niche": _dominant_niche(videos),
        "top_videos": top,
        "weak_videos": weak,
        "recommended_focus": [
            "impossible engineering mechanics",
            "animal intelligence and biology",
            "hidden technology and computing history",
            "concrete natural phenomena"
        ]
    }


def decide(market, memory):
    recent = memory.get("videos", [])[-30:]
    summary = _performance_summary(memory.get("videos", []))
    prompt = (RULES
              + "\n\nCHANNEL IDENTITY:\n" + json.dumps(_identity(memory), ensure_ascii=False)
              + "\n\nPERFORMANCE SUMMARY:\n" + json.dumps(summary, ensure_ascii=False)
              + "\n\nMARKET DATA:\n" + json.dumps(market, ensure_ascii=False)[:6000]
              + "\n\nRECENT MEMORY RECORDS (raw):\n"
              + json.dumps(recent, ensure_ascii=False)[:5000]
              + "\n\nLESSONS LEARNED:\n" + json.dumps(memory.get("lessons", [])[-15:], ensure_ascii=False)
              + "\n\n" + FORMAT)
    return _ask(prompt)
