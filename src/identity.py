import json
from market import collect
from agent import _ask

prompt = ("You are the AI that must create a brand new YouTube Shorts channel in "
          "English, targeting a global (worldwide) audience, meant to grow "
          "autonomously. Market data: "
          + json.dumps(collect(), ensure_ascii=False)[:6000]
          + ". Choose a niche, a channel name (original, max 30 characters), a "
          "handle, a bio (max 300 characters, disclose that the channel is "
          "AI-run), a personality/tone, a color palette, an English prompt to "
          "generate the avatar and the banner, and 5 first video ideas. "
          "Reply ONLY in JSON.")

if __name__ == "__main__":
    print(json.dumps(_ask(prompt), ensure_ascii=False, indent=2))