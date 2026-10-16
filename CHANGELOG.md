# Changelog

## Unreleased — reliability & free-tier hardening

All changes keep the project free and fully automatic.

- **Robust LLM fallback** (`agent.py`): a bad/retired model name no longer
  aborts the whole chain. Only a daily-quota error or a temporary overload
  (`503`) is handled specially; any other failure now falls through to the
  next model. `decide()` also receives the channel identity, and the niche
  focus is derived from what the channel has actually published, so the
  prompt stays coherent.
- **Prompt/guardrail alignment** (`agent.py`/`guardrails.py`): the script
  length bounds now agree (55–150 words, targeting the 70–120 the prompt
  asks for), a short call-to-action was added to the script rules, and the
  duplicate check normalises titles (so "Hello, World!" and "hello world"
  are recognised as the same).
- **Serialised runs + safe push** (`.github/workflows/daily.yml`): a
  `concurrency` group stops overlapping runs from racing on `memory.json`,
  and the memory commit now pulls/rebase-retries before pushing instead of
  failing on the first conflict.
- **Optional free alerting**: heartbeat/healthcheck and failure
  notifications via `HEALTHCHECK_URL` / `NTFY_URL` secrets (no-op if unset).
- **Production robustness** (`produce.py`): clip search and downloads check
  the HTTP status and skip bad files instead of crashing the run; ffmpeg and
  Piper errors are now logged instead of hidden; the final audio is
  loudness-normalised (`loudnorm`, −14 LUFS).
- **Metrics failures no longer block publishing** (`main.py`): a YouTube API
  hiccup while reading stats is logged and the run continues; a production or
  upload failure is recorded as a lesson before re-raising.
- **Metadata** (`upload.py`): YouTube category set to Education (27), English
  description fixed, audio language declared.
- **Reproducibility**: dependencies pinned in `requirements.txt`; Whisper
  model cache added to CI; stray empty `git` file removed.

## v0.1.0-alpha — first public release

Initial release of the experiment: an autonomous AI agent that analyzes
market trends, decides on content, produces a narrated short video, uploads
it to YouTube Shorts, reads back the results, and learns over time. Built
entirely on free-tier tools.

This is an **alpha**: the core loop works end to end, but it has only been
tested by one person, on one channel, for a few days. Expect rough edges.

### Fixed during development (worth knowing if you fork this)

- **Language mismatch bug**: the planning prompt (`agent.py`) was still in
  Italian while the voice and transcription were set to English, so the
  generated speech was mispronounced and the subtitles came out as garbled
  nonsense. The whole pipeline — prompt, voice, Whisper transcription,
  YouTube metadata — must use the *same* language end to end.
- **Memory never persisted**: an early workflow had `working-directory: src`
  on the step that runs `main.py`, but the step that commits `memory/` back
  to the repo ran from the project root. The agent's memory was written to
  `src/memory/` and silently discarded at the end of every run, so it never
  actually learned anything. Fixed by running `python src/main.py` from the
  repo root so both steps agree on where `memory/` lives.
- **Gemini model name churn**: Google retired `gemini-2.5-flash` for new
  projects, then `gemini-2.0-flash`, mid-project. `agent.py` now tries a
  list of models in order (`MODELS`) and falls back automatically instead
  of hardcoding one name.
- **Gemini free-tier quota**: new API keys get a very small daily quota
  (as low as 20 requests/day) on the newest models. Removed a redundant
  second LLM call per attempt (a separate "safety review" pass) to roughly
  halve quota usage; local keyword-based guardrails cover basic safety for
  free instead.

### Known limitations

- Voice quality is "free TTS" quality (edge-tts), not studio-grade — this
  was an intentional trade-off for zero cost.
- Whisper `base` on a shared CPU runner is decent but not perfect; expect
  occasional subtitle errors, especially on names/jargon.
- TikTok and Instagram are not implemented (see the README — YouTube only
  for now).
- The Google OAuth app needs to pass Google's "sensitive scope" verification
  to avoid the 7-day test-mode token expiry; until then, the token must be
  regenerated manually every 7 days.
- No automated tests. This was built interactively, file by file, and
  debugged against real runs.
