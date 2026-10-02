import os
import json
import time
from google import genai

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

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
    "RULES: (1) use the market data and the memory of past results; "
    "(2) about 70% of the time stick to niches/formats that performed well, "
    "30% experiment with something new; (3) never repeat topics or titles "
    "already published; (4) only true, verifiable, useful or entertaining content; "
    "forbidden: misinformation, medical/financial/legal advice, partisan politics, "
    "defamation of real people, hate speech, adult content; (5) spoken script "
    "25-45 seconds long (70-120 words), with a hook in the first 2 seconds; "
    "(6) never attribute invented quotes to real people; (7) write the script "
    "entirely in English, since it will be read aloud by an English voice."
)

FORMAT = (
    "Reply ONLY with JSON with these keys: "
    "niche, topic, title (max 70 characters), script (spoken text, in English), "
    "keywords (list of 5-8 English keywords for stock footage search), "
    "description, hashtags (list, max 5), rationale (why you chose this)."
)


def _ask(prompt):
    """Calls Gemini: tries models in order, immediately falls back to
    the next one if the quota is exhausted, retries with backoff if the
    server is just temporarily overloaded."""
    last_error = None
    for model in MODELS:
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={"response_mime_type": "application/json"}
                )
                return json.loads(resp.text)
            except Exception as e:
                last_error = e
                error_str = str(e)
                if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str:
                    print(f"⚠️ Quota exhausted for {model}, trying the next model...")
                    break  # no point retrying the same model: it's a daily quota
                elif "503" in error_str or "UNAVAILABLE" in error_str:
                    wait_time = 5 * (attempt + 1)
                    print(f"⏳ {model} is busy, retrying in {wait_time}s... (attempt {attempt + 1}/3)")
                    time.sleep(wait_time)
                else:
                    raise
    raise last_error


def decide(market, memory):
    recent = memory.get("videos", [])[-30:]
    prompt = (RULES + "\n\nMARKET DATA:\n" + json.dumps(market, ensure_ascii=False)[:6000]
              + "\n\nMEMORY (past videos and their results):\n"
              + json.dumps(recent, ensure_ascii=False)[:6000]
              + "\n\nLESSONS LEARNED:\n" + json.dumps(memory.get("lessons", [])[-15:], ensure_ascii=False)
              + "\n\n" + FORMAT)
    return _ask(prompt)
