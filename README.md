<h1 align="center">Melodi AI</h1>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB" />
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.162-009688" />
  <img alt="Claude" src="https://img.shields.io/badge/LLM-Claude%20Haiku%205.5-D97757" />
  <img alt="Tests" src="https://img.shields.io/badge/tests-pytest-0A9EDC" />
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green" />
</p>

**A context-aware AI DJ.** It turns a listener's moment (time of day, weather, whether they're driving or walking, where they are, how they feel, or a sentence like *"long drive to Vizag at night"*) into a 25-song mix of real songs, each with a one-line reason.

Built with **Python · FastAPI · the Anthropic SDK (Claude, structured outputs) · ytmusicapi · Pydantic**.

> [!IMPORTANT]
> **Built for experimentation and learning, not as a product.** I made Melodi AI to learn how to build reliable LLM features: structured outputs, keeping the model grounded in real data, cost and latency trade-offs, and testing the non-AI parts. It isn't affiliated with or endorsed by YouTube, Google or Anthropic. See the [disclaimer](#disclaimer).

## Example

One real request: *Wednesday 9:40 pm, light rain, 24°C, driving, Hyderabad, mood "calm", "long drive, soft melodies", favourite artists Sid Sriram, M.M. Sreelekha, Anirudh.*

> **🌧️ Rain-Soft Roads Through Hyderabad Night**
> *A gentle, rain-washed sequence that eases you through Hyderabad's late-night streets with Sid Sriram and Anirudh at its heart.*
>
> 1. **Maate Vinadhuga** · Sid Sriram: *gentle voice opens softly for the rainy night drive*
> 2. **Nuvvunte Chaley** · Anirudh Ravichander: *understated melody settles the car into a calm rhythm*
> 3. **Chuttamalle** · Shilpa Rao: *soothing vocals keep the mood warm and unhurried*
> 4. **Chamkeela Angeelesi (Rainy Lofi)**: *lofi texture matches the light rain on the windscreen*
> 5. … 20 songs in total, drawn from *Tollywood Romance*, *Tollywood Essentials*, *Night Drive* and others
>
> Claude Haiku 5.5 · 3 LLM calls · ~8K input tokens · **≈ $0.002 per mix** · 14 s

---

## The problem with "just ask an LLM for songs"

The obvious design is to ask an LLM *"give me rainy-night Telugu songs"* or to run its words through YouTube search. Both are unreliable. The LLM can invent songs, and search returns whatever matches the words, with nothing checking that a song actually *sounds* like a rainy night.

Melodi uses the LLM for what it's good at (**understanding context and making judgement calls between real options**) and takes the songs from **human-curated sources**.

## How it works

```mermaid
%%{init: {"themeVariables": {"fontSize": "20px"}, "flowchart": {"nodeSpacing": 30, "rankSpacing": 40, "padding": 16}}}%%
flowchart TD
    A["📱 <b>Your moment</b><br/>time · weather · place · mood"]
    B["🧠 <b>1. Understand</b><br/>Claude reads the moment"]
    C["🔎 <b>2. Narrow</b><br/>3,364 playlists → ~150"]
    D["🧠 <b>3. Pick</b><br/>Claude chooses 3–6 playlists"]
    E["🎵 <b>4. Collect</b><br/>real songs + your radio"]
    F["📊 <b>5. Score</b><br/>rank and trim to top 40"]
    G["🧠 <b>6. Sequence</b><br/>Claude orders the mix"]
    H["▶️ <b>Your mix</b><br/>25 songs, each with a reason"]
    A --> B --> C --> D --> E --> F --> G --> H
    classDef ai fill:#efe7ff,stroke:#8b5cff,stroke-width:2px,color:#1a1a1a
    classDef code fill:#e6f4ff,stroke:#2f80ed,stroke-width:2px,color:#1a1a1a
    classDef phone fill:#ffe8ef,stroke:#ff3d6e,stroke-width:2px,color:#1a1a1a
    class B,D,G ai
    class C,E,F code
    class A,H phone
```

<p align="center"><sub>🧠 purple = Claude (structured output) · blue = plain code · pink = the phone</sub></p>

1. **Understand.** Claude reads the moment and returns a `MusicTarget`: which of YouTube Music's 39 mood and genre categories fit, title keywords (e.g. *Tollywood*), languages, and target **energy** and **valence**. Valence (sad ↔ happy) and arousal (calm ↔ energetic) are the two axes music-emotion research uses.
2. **Narrow.** YouTube Music's *Moods & genres* section holds ~3,400 editor-curated playlists, each labelled by category and shelf (e.g. *Sad › Bollywood sad*). Sending them all on every request would cost ~40K tokens, so code filters them to ~150 using the target's categories and keywords.
3. **Pick.** Claude chooses 3–6 playlists from that numbered shortlist. **Every number is checked in code**, so a hallucinated pick is simply dropped.
4. **Collect.** The chosen playlists' real tracks, plus YouTube radio seeded from songs the listener has liked *that also appear in today's picks* (fits both mood and taste).
5. **Score.** A transparent, deterministic ranking: songs several curated lists agree on score highest, then favourite artists and radio. Different uploads of the same song (lyric video, official video, audio) are merged first, keeping the official audio and crediting every playlist any version appeared in. Recently played songs are dropped, and each artist is capped at 3.
6. **Sequence.** Claude orders the best 40 into a smooth energy flow and writes the title, description and a short "why" for each song. Code again validates every number and tops up from the scores if needed.

**Design principles**
- **The LLM chooses, code verifies.** Claude only ever returns numbers from lists the code gave it, so it can't invent playlists or songs.
- **Structured outputs everywhere.** Each step returns a Pydantic model (`MusicTarget`, `PlaylistPicks`, `MixPlan`) through `client.beta.messages.parse(output_format=...)`, so there's no regex parsing of free text.
- **Deterministic where it can be.** Narrowing, collecting and scoring are plain code with unit tests. Results are reproducible, and cost and latency are predictable.
- **Cost and latency aware.** Three short calls at low effort instead of one huge prompt. Token usage and timing are returned with every response (`usage`).
- **Privacy.** The phone turns location into labels ("driving", "Hyderabad", "light rain, 24°C"). GPS coordinates never reach this server, and nothing is stored.
- **Resilient.** If a playlist fails to load, the mix still works. Server-side refusal fallbacks are enabled, and errors map to clear HTTP statuses.

## API

`POST /v1/plan`

```json
{
  "size": 25,
  "context": {
    "local_time": "2026-10-28T21:40:00+05:30",
    "daypart": "night",
    "weather": "light rain, 24°C",
    "activity": "driving",
    "city": "Hyderabad",
    "country_code": "IN",
    "mood": "calm",
    "description": "long drive, soft melodies",
    "taste": { "top_artists": ["Sid Sriram"], "liked_video_ids": [], "recent_video_ids": [] }
  }
}
```

The response has `title`, `description`, the `target`, the `sources` (curated playlists used), `tracks` (each with `why`) and `usage` (model, tokens, LLM calls, seconds). `GET /health` reports status and model.

## Run it locally

Requires [uv](https://docs.astral.sh/uv/) and an [Anthropic API key](https://console.anthropic.com/settings/keys).

```bash
cd melodi-ai
cp .env.example .env          # then paste your ANTHROPIC_API_KEY into .env
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8787
```

### Using it from a phone app

[`clients/react-native/`](clients/react-native) has a ready-made client for Expo/React Native apps:
- `context.ts` senses the moment on the device: time of day and sunset, weather from Open-Meteo, whether you're walking or driving, and the city. It turns all of that into labels, so GPS coordinates never reach the server.
- `melodiClient.ts` calls `POST /v1/plan` and returns typed tracks.

Point your app at the server (phone and Mac on the same Wi-Fi):
1. In your app, set `EXPO_PUBLIC_MELODI_URL=http://<your Mac's name>.local:8787`. Find the name with `scutil --get LocalHostName`. A `.local` name keeps working when the router gives the Mac a new IP.
2. Put the same random value in `MELODI_APP_TOKEN` (server `.env`) and `EXPO_PUBLIC_MELODI_TOKEN` (app), so only your app can spend your API credit. Generate one with `python3 -c "import secrets; print(secrets.token_urlsafe(24))"`.
3. Add `expo-location` to the app, with a `locationWhenInUsePermission` message and an `NSLocalNetworkUsageDescription` in `app.json`, then rebuild. On first use, iOS asks for **Location** and **Local Network** access.
4. If the phone can't connect, the macOS Firewall is probably blocking it: System Settings → Network → Firewall → Options → allow incoming connections for `python3.12`.

## Tests

```bash
uv run pytest
```

These cover the deterministic core: target cleaning, catalogue narrowing, rejecting invented playlist numbers, scoring and artist caps, and assembling the final order.

## Code map

| File | Role |
|---|---|
| `app/main.py` | FastAPI app, optional `X-Melodi-Token` check, error → HTTP mapping |
| `app/planner.py` | The pipeline and the three prompts |
| `app/llm.py` | The only Claude call site: structured output, effort, fallbacks, usage accounting |
| `app/catalog.py` | Loads and caches (24 h, per country) YouTube Music's curated Moods & genres playlists |
| `app/candidates.py` | Collects real tracks and scores them |
| `app/models.py` | Request, response and structured-output schemas |

## Roadmap

- **Evals:** a scenario set ("rainy night, sad, Telugu", "gym, hype, English"…) scored by rules plus an LLM judge, run in CI.
- **Taste embeddings:** listening history in Supabase pgvector, for better taste matching.
- **🎬 Shot here:** songs from films shot in the listener's city, using Wikidata filming locations → soundtrack albums.
- **Audio features:** on-audio mood estimates (e.g. Essentia arousal/valence, CLAP text-to-audio similarity) to check that a song really sounds calm or energetic.
- **Tool-use agent:** expose catalogue search, candidate collection and scoring as separately defined tools so Claude can iterate when a mix looks weak.

## Disclaimer

**This project exists only for experimentation, learning and study.**
- Melodi AI reads public YouTube Music catalogue pages through [ytmusicapi](https://github.com/sigma67/ytmusicapi). It is not affiliated with, endorsed by or connected to YouTube, Google or Anthropic. "YouTube Music" is a trademark of Google LLC.
- Automated access to YouTube may conflict with YouTube's Terms of Service. Use this for learning, not for any commercial purpose or to redistribute content.
- All music, artwork and metadata belong to their respective owners.
- The code is provided as-is, with no warranty.

## License

[MIT](LICENSE), for the code in this repository only. It grants no rights to any music, artwork or other content.
