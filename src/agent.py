import os
import json
import time
from google import genai

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL = "gemini-3.8-flash"   # verifica il nome del modello disponibile

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
    """Chiede a Gemini, con retry automatico se Google è occupato"""
    max_attempts = 5
    
    for attempt in range(max_attempts):
        try:
            resp = client.models.generate_content(
                model=MODEL, 
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            return json.loads(resp.text)
        
        except Exception as e:
            error_str = str(e)
            
            # Se è un errore 503 (Google occupato) e non è l'ultimo tentativo, riprova
            if "503" in error_str and attempt < max_attempts - 1:
                wait_time = 2 ** attempt + 2  # 3, 4, 6, 10, 18 secondi
                print(f"⏳ Google occupato, riprovo tra {wait_time}s... (tentativo {attempt + 1}/{max_attempts})")
                time.sleep(wait_time)
            else:
                # Se non è 503 o è l'ultimo tentativo, fallisci
                raise

def decide(market, memory):
    recent = memory.get("videos", [])[-30:]
    prompt = (RULES + "\n\nDATI DI MERCATO:\n" + json.dumps(market, ensure_ascii=False)[:6000]
              + "\n\nMEMORIA (video passati e risultati):\n"
              + json.dumps(recent, ensure_ascii=False)[:6000]
              + "\n\nLEZIONI APPRESE:\n" + json.dumps(memory.get("lessons", [])[-15:], ensure_ascii=False)
              + "\n\n" + FORMAT)
    return _ask(prompt)

def review(plan):
    prompt = ("Sei un revisore di sicurezza per contenuti video. Valuta questo piano: "
              + json.dumps(plan, ensure_ascii=False)
              + ". Rispondi SOLO con JSON: {\"ok\": true/false, \"reason\": \"...\"}. "
              "ok=false se contiene disinformazione, consigli medici/finanziari/legali, "
              "diffamazione, odio, contenuti sessuali o violazioni di copyright.")
    return _ask(prompt)