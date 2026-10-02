# Changelog

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
