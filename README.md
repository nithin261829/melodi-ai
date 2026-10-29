# Melodi AI

An AI DJ that reads your moment (time, weather, whether you're driving, your mood) and builds a playlist of real songs, with a reason for each one.

Python · FastAPI · Anthropic SDK (Claude Haiku 5.5) · tool calling · structured outputs · 22 tests · MIT

> A learning project, not a product. Not affiliated with YouTube, Google or Anthropic.

## Example

- **Input:** 9:40 pm · light rain · driving · Hyderabad · mood "calm" · likes Sid Sriram
- **Output:** *Rain-Soft Roads Through Hyderabad Night*, 20 calm Telugu songs, ~$0.002, 14 s

```
1. Maate Vinadhuga · Sid Sriram       gentle voice opens softly for the rainy drive
2. Nuvvunte Chaley · Anirudh          understated melody, calm rhythm
3. Chuttamalle · Shilpa Rao           soothing vocals, warm and unhurried
```

## Why I built it

Music apps suggest songs from what you played before, not from where you are. I wanted a DJ that notices it's raining, late, and you're driving, and picks songs for *that*. I also wanted to learn how to build an LLM feature that can't make things up: an LLM asked for "rainy night songs" will happily invent songs that don't exist. So the songs here only ever come from real, human-curated playlists, and the model just makes the judgement calls.

## How it works

```text
Melo app (iPhone)
  │  labels only: time · weather · driving · city · mood · top artists
  ▼
FastAPI service
  ├─ pipeline (default)  code runs 6 steps, the LLM makes 3 decisions
  └─ agent               the LLM calls 5 tools itself:
       search_catalog → get_playlist_tracks → get_radio
       → rank_candidates → finish_mix
  ▼
25 real songs + a reason for each
```

1. The LLM decides what the moment needs: moods, languages, energy.
2. It picks from YouTube Music's 3,364 human-curated mood playlists.
3. Code loads the real songs, removes duplicates and scores them.
4. The LLM orders the best ones and writes a reason for each.

The model only ever picks numbers from lists the code gives it, and code checks every one, so it can't invent songs.

## How it's built

- **A catalogue I could trust.** Instead of free-text search, Melodi reads YouTube Music's 3,364 editor-curated Moods & genres playlists, each labelled by mood and language (for example *Sad › Bollywood sad*). `ytmusicapi` crashed on some of those pages, so I wrote my own tolerant parser, load the 39 categories in parallel, and cache them per country for 24 hours.
- **Small prompts, not one giant one.** Sending all 3,364 playlists would be about 40K tokens per request. Code first narrows them to the ~150 that match the moment's keywords and categories, so each LLM call stays at 2–4K tokens.
- **The model picks numbers, code checks them.** Every list the model sees is numbered, its answers come back as validated Pydantic objects (structured outputs), and any number that wasn't on the list is dropped. That's why it can't invent a song.
- **Plain, testable scoring.** Songs score +2 for each chosen playlist they appear in, up to +0.5 for being near the top, +1.5 for a favourite artist and +1 for radio from a liked song. Recent plays are dropped, each artist is capped at 3, and different uploads of the same song (lyric video, official audio) are merged.
- **Two ways to plan.** The pipeline runs fixed steps. The agent gets five tools, each with its own strict JSON schema, and decides what to call. Its loop is capped at 10 rounds, records every call, and falls back to the pipeline if anything fails.
- **Cheap on purpose.** I measured Claude Opus 5.5 against Claude Haiku 5.5 on the same request. The mixes were similar, but Haiku was about 29 times cheaper, so it's the default.
- **Privacy and safety.** The server never sees GPS, only labels. The API key stays in a git-ignored `.env`, an app token stops anyone else spending the credit, and nothing is stored.
- **Tested where bugs live.** 22 unit tests cover everything around the model. The lite evals run 12 real scenarios through both modes; they caught the same artist playing twice in a row, which is now fixed in code.

## Results

| | Pipeline | Agent |
|---|---|---|
| Cost per mix | $0.0014 | $0.0030 |
| Time per mix | 12 s | 14 s |
| Lite evals (12 scenarios) | 102/102 | 102/102 |

The evals caught the same artist playing twice in a row. That's now fixed in code.

## Run it

```bash
cp .env.example .env    # add your ANTHROPIC_API_KEY
uv sync
uv run uvicorn app.main:app --port 8787
```

`POST /v1/plan` with the context and optionally `"mode": "agent"`. Tests: `uv run pytest`. Evals: `uv run python -m evals.run`.

## Code

| File | What it does |
|---|---|
| `app/planner.py` | The pipeline |
| `app/agent.py`, `app/tools.py` | The agent loop and its 5 tools (JSON schemas) |
| `app/candidates.py` | Collects and scores real songs |
| `app/catalog.py` | Loads and caches the curated playlists |
| `evals/` | 12 scenarios with rule checks |

## License

[MIT](LICENSE), for the code only. Music, artwork and metadata belong to their owners. Reading YouTube Music through [ytmusicapi](https://github.com/sigma67/ytmusicapi) may conflict with YouTube's Terms of Service, so this is for learning only.
