import json
from market import collect
from agent import _ask

prompt = ("Sei l'AI che deve creare da zero un canale YouTube Shorts in italiano per "
          "diventare famoso in modo autonomo. Dati di mercato: "
          + json.dumps(collect(), ensure_ascii=False)[:6000]
          + ". Scegli nicchia, nome del canale (originale, max 30 caratteri), handle, "
          "bio (max 300 caratteri, dichiara che il canale e' gestito da un'AI), "
          "personalita'/tono, palette colori, prompt in inglese per generare "
          "l'avatar e il banner, e 5 idee di primi video. Rispondi SOLO in JSON.")

if __name__ == "__main__":
    print(json.dumps(_ask(prompt), ensure_ascii=False, indent=2))
