import os
import json
import time
from google import genai

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# Ordine di preferenza: il primo modello ha in genere la quota gratuita
# giornaliera piu' alta. Se un modello finisce la quota o non risponde,
# si passa automaticamente al successivo. Se questi nomi diventano
# obsoleti, controlla https://ai.google.dev/gemini-api/docs/models
MODELS = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash"]

RULES = (
    "Sei l'agente autonomo che gestisce un canale YouTube Shorts in italiano. "
    "Il tuo obiettivo e' far crescere il canale (visualizzazioni, retention, iscritti) "
    "in modo autonomo e onesto. Decidi tu nicchia, argomento e stile. "
    "REGOLE: (1) usa i dati di mercato e la memoria dei risultati; "
    "(2) circa il 70% delle volte insisti su formati/nicchie che hanno performato bene, "
    "il 30% sperimenta qualcosa di nuovo; (3) non ripetere argomenti o titoli gia' "
    "pubblicati; (4) solo contenuti veri, verificabili, utili o divertenti; "
    "vietati: disinformazione, consigli medici/finanziari/legali, politica di parte, "
    "persone reali diffamate, odio, contenuti per adulti; (5) script parlato di "
    "25-45 secondi (70-120 parole), con un aggancio nei primi 2 secondi; "
    "(6) non citare persone reali come autori di frasi inventate."
)

FORMAT = (
    "Rispondi SOLO con JSON con queste chiavi: "
    "niche, topic, title (max 70 caratteri), script (testo parlato), "
    "keywords (lista di 5-8 parole chiave in INGLESE per cercare clip stock), "
    "description, hashtags (lista, max 5), rationale (perche' hai scelto questo)."
)


def _ask(prompt):
    """Chiede a Gemini: prova piu' modelli in ordine, salta subito al
    successivo se la quota e' esaurita, riprova con attesa se il server
    e' solo temporaneamente occupato."""
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
                    print(f"⚠️ Quota esaurita per {model}, provo il modello successivo...")
                    break  # niente retry sullo stesso modello: e' quota giornaliera
                elif "503" in error_str or "UNAVAILABLE" in error_str:
                    wait_time = 5 * (attempt + 1)
                    print(f"⏳ {model} occupato, riprovo tra {wait_time}s... (tentativo {attempt + 1}/3)")
                    time.sleep(wait_time)
                else:
                    raise
    raise last_error


def decide(market, memory):
    recent = memory.get("videos", [])[-30:]
    prompt = (RULES + "\n\nDATI DI MERCATO:\n" + json.dumps(market, ensure_ascii=False)[:6000]
              + "\n\nMEMORIA (video passati e risultati):\n"
              + json.dumps(recent, ensure_ascii=False)[:6000]
              + "\n\nLEZIONI APPRESE:\n" + json.dumps(memory.get("lessons", [])[-15:], ensure_ascii=False)
              + "\n\n" + FORMAT)
    return _ask(prompt)
