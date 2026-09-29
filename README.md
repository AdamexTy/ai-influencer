# ai-influencer

Progetto sperimentale: un agente AI che gestisce in autonomia un canale
YouTube Shorts (analizza il mercato, decide, produce video con voce e
sottotitoli, pubblica, legge i risultati e impara).

## Stato di questa versione

Rispetto alla guida PDF originale, qui sono gia' applicate queste correzioni:

- `src/agent.py`: usa una lista di modelli Gemini di riserva
  (`gemini-3.5-flash-lite` per primo, che ha la quota gratuita piu' alta),
  e salta automaticamente al modello successivo se uno esaurisce la quota
  giornaliera (errore 429) o e' temporaneamente occupato (errore 503).
  Rimossa la funzione `review()` per dimezzare il consumo di quota: il
  controllo di sicurezza resta comunque attivo tramite `guardrails.py`
  (locale, gratuito, senza chiamate API).
- `src/main.py`: non chiama piu' `review()`; gestisce con un `try/except`
  gli errori di Gemini durante il ciclo di tentativi, cosi' non va in
  crash e salva comunque la memoria.
- `.github/workflows/daily.yml`: rimosso `working-directory: src` dallo
  step "Esegui agente" (bug che faceva salvare la memoria nella cartella
  sbagliata, mai committata su GitHub). Ridotto a **un run al giorno**
  (invece di due) per non esaurire la quota gratuita di Gemini durante i
  test iniziali; il secondo cron e' commentato e pronto da riattivare.
- Aggiunto `src/identity.py` (Fase 12 della guida): genera nicchia, nome,
  bio, tono, palette e prompt per l'avatar del canale.

## Cosa manca da fare tu (manuale)

1. Copia il tuo `client_secret.json` (scaricato da Google Cloud) nella
   cartella principale, accanto a `requirements.txt`. Non va mai committato
   (e' gia' nel `.gitignore`).
2. `pip install -r requirements.txt`
3. `cd src && python get_token.py` per ottenere `YT_REFRESH_TOKEN`,
   `YT_CLIENT_ID`, `YT_CLIENT_SECRET`.
4. Inserisci su GitHub (Settings > Secrets and variables > Actions) i 6
   secrets: `GEMINI_API_KEY`, `PEXELS_API_KEY`, `YOUTUBE_API_KEY`,
   `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.
5. Settings > Actions > General > Workflow permissions > "Read and write".
6. Esegui `python identity.py` (dentro `src/`, con `GEMINI_API_KEY` e
   `YOUTUBE_API_KEY` come variabili d'ambiente) per farti proporre nome,
   bio e nicchia del canale, e applicali a mano su YouTube Studio.
7. Lancia il workflow manualmente da Actions > ai-influencer > Run workflow.

## Nota sulla quota gratuita di Gemini

I modelli Gemini 3.x hanno una quota gratuita molto bassa (circa 20
richieste al giorno per modello, per i progetti nuovi). Il codice prova
piu' modelli in sequenza per non restare bloccato, ma se fai molti test
manuali nello stesso giorno puoi comunque esaurirla: la quota si resetta
a mezzanotte, fuso orario del Pacifico (le 8-9 del mattino in Italia).
