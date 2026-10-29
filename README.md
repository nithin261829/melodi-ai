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
