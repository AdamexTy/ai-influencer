# ai-influencer

**v0.1.0-alpha**

An experiment: can an AI agent run a YouTube Shorts channel completely on
its own — picking the niche, writing the scripts, producing the video with
voice and subtitles, publishing it, reading back the results, and adjusting
strategy — using only free tools?

This repository is the result of that experiment, running as of this
release. It is **alpha-quality**: functional end to end, but tested by one
person on one channel for a short time. Read the "Known limitations" section
in [CHANGELOG.md](./CHANGELOG.md) before relying on it.

## How it works

```
[GitHub Actions cron]
        |
        v
Read past metrics ---> [ memory/memory.json ] <---------------+
        |                                                      |
        v                                                      |
Market scan (YouTube trending, Hacker News, Wikipedia)         |
        |                                                      |
        v                                                      |
Gemini decides: niche, topic, script, title, keywords          |
        |                                                      |
        v                                                      |
Local guardrails ---rejected---> log a lesson ------------------+
        |
        v
Voice (edge-tts) + stock clips (Pexels) + subtitles (Whisper) + FFmpeg
        |
        v
Upload to YouTube ---> save video id to memory
```

Everything after the one-time setup below runs unattended, on a schedule,
on GitHub's free Actions runners — no computer needs to stay on.

## What's free, and what the free tier actually gives you

| Purpose | Tool | Free tier, roughly |
|---|---|---|
| Hosting / scheduling | GitHub Actions | Unlimited on public repos |
| Decision-making (LLM) | Gemini API | **As low as 20 requests/day** per model on new projects — see note below |
| Voice | edge-tts | Free, unofficial use of Microsoft's voices |
| Stock video | Pexels API | Free with a key |
| Video editing | FFmpeg | Open source |
| Subtitles | faster-whisper (`base` model) | Open source, runs on CPU |
| Publishing + stats | YouTube Data API v3 | 10,000 units/day; one upload costs ~1,600 |

**About the Gemini quota**: this was the single biggest practical surprise
building this. New Gemini API projects can be locked out of older,
higher-quota models (e.g. `gemini-2.5-flash`) and pushed onto newer models
with a much smaller free daily quota. `src/agent.py` tries a list of models
and falls back automatically, but if you run several manual tests in the
same day you can still hit the wall. The quota resets at midnight Pacific
Time. Check https://ai.google.dev/gemini-api/docs/rate-limits for current
numbers before you plan a schedule.

## One-time setup (human required)

A few steps genuinely require a person — Google won't let a script do them:

1. **Create a Google account and a YouTube channel** for this experiment
   (a Brand Account under your existing Google account works fine, you
   don't need a separate Google login).
2. **Google Cloud project**: console.cloud.google.com → new project →
   enable **YouTube Data API v3**.
3. **API key**: APIs & Services → Credentials → Create credentials → API
   key. Restrict it to YouTube Data API v3. This is `YOUTUBE_API_KEY`.
4. **OAuth consent screen** (now called "Google Auth Platform" in some
   accounts): External user type, add yourself as a test user, add scopes
   `youtube.upload`, `youtube.readonly`, `yt-analytics.readonly`.
   - To publish the app (recommended — otherwise your refresh token expires
     every 7 days), Google will ask for a homepage and a privacy policy URL
     it can verify you own. The simplest free option is a two-page GitHub
     Pages site verified through Google Search Console (URL-prefix
     property, HTML tag method).
   - YouTube scopes are classified as "sensitive", so full verification can
     take Google a few business days. This is one-time.
5. **OAuth client**: Credentials → Create credentials → OAuth client ID →
   Desktop app. Download the JSON, or copy the Client ID/Secret manually
   into a file named `client_secret.json` at the repo root:
   ```json
   {
     "installed": {
       "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
       "project_id": "your-project-id",
       "auth_uri": "https://accounts.google.com/o/oauth2/auth",
       "token_uri": "https://oauth2.googleapis.com/token",
       "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
       "client_secret": "YOUR_CLIENT_SECRET",
       "redirect_uris": ["http://localhost"]
     }
   }
   ```
   This file is gitignored — never commit it.
6. **Gemini API key**: aistudio.google.com → Get API key.
7. **Pexels API key**: pexels.com/api.
8. **Get a refresh token** (one time, locally):
   ```
   pip install -r requirements.txt
   cd src
   python get_token.py
   ```
   Sign in with the account that owns the YouTube channel, accept the
   "unverified app" warning (Advanced → Go to [app name]), and copy the
   three values it prints.
9. **GitHub repo secrets**: Settings → Secrets and variables → Actions →
   add `GEMINI_API_KEY`, `PEXELS_API_KEY`, `YOUTUBE_API_KEY`, `YT_CLIENT_ID`,
   `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.
10. **Workflow permissions**: Settings → Actions → General → Workflow
    permissions → **Read and write permissions** (needed so the agent can
    commit its memory back to the repo).
11. **Channel identity** (optional but recommended): let the AI pick a
    name, bio, niche and tone for the channel instead of hardcoding one:
    ```
    set GEMINI_API_KEY=...
    set YOUTUBE_API_KEY=...
    python identity.py
    ```
    Apply the result by hand in YouTube Studio → Customization (name,
    handle, bio, avatar/banner — use the generated image prompts on any
    free image generator). This step can't be automated: YouTube channel
    branding isn't reliably scriptable.

Everything after this runs on its own via the `daily.yml` workflow.

## Project structure

```
ai-influencer/
  .github/workflows/daily.yml   automation (schedule + manual trigger)
  src/
    market.py       free market signals: YouTube trending, Hacker News, Wikipedia
    agent.py         talks to Gemini; decides niche/topic/script; model fallback
    guardrails.py     local, free safety/sanity checks (no API calls)
    produce.py        voice (edge-tts) + clips (Pexels) + subtitles (Whisper) + FFmpeg
    upload.py          publishes to YouTube, declares synthetic media
    feedback.py        reads back view/like/subscriber counts into memory
    main.py             orchestrates one full run
    get_token.py        one-time: obtains the YouTube OAuth refresh token
    identity.py          one-time: asks Gemini to design the channel's identity
  memory/memory.json   the agent's own memory: past videos, results, lessons learned
  requirements.txt
  .gitignore
```

## Running it manually

From the repo root: Actions tab → `ai-influencer` → **Run workflow**. Watch
the logs under the "Run the agent" step. A full run (market scan, LLM
decision, voice, clips, subtitles, FFmpeg encode, upload) typically takes
5–15 minutes on GitHub's shared runners — longest on the very first run,
since the Whisper model has to download.

## Safety guardrails already in place

- Local keyword blocklist (medical/financial/legal advice, politics,
  adult content, etc.) in `guardrails.py` — free, no API call.
- Script length bounds and duplicate-title checks.
- `containsSyntheticMedia: true` is set on every upload, disclosing
  AI-generated content to YouTube and viewers.
- Max 3 planning attempts per run, 45-minute workflow timeout.
- A 70/30 "exploit vs explore" instruction baked into the prompt, so the
  agent mostly repeats what works but keeps experimenting.

None of this guarantees good judgment from the model — review what it
publishes, especially early on.

## Extending beyond YouTube

Not implemented here. TikTok's Content Posting API and Instagram's Graph
API both require their own OAuth app, and TikTok posts stay private until
your app passes their audit. If you add either, a multi-platform scheduler
like Postiz (open source, self-hosted) may be less work than writing both
integrations by hand.

## License

MIT — see [LICENSE](./LICENSE). Use, fork, and modify freely; no warranty.

## Contributing / forking

If you fork this for your own channel:
- Never reuse someone else's `client_secret.json`, API keys, or refresh
  token — each channel needs its own.
- Run `identity.py` (or write your own niche/bio by hand) so your channel
  doesn't start out as a clone of whatever channel this was built for.
- `memory/memory.json` ships empty in this repo (`{"channel": {}, "videos":
  [], "lessons": []}`) — the agent fills it in as it runs.
