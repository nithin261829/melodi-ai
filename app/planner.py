"""The Melodi pipeline: understand the moment -> pick curated playlists -> score songs -> order the mix.

The LLM only ever chooses from lists the code gives it, and the code checks every number it returns,
so it can shape the mix but cannot invent songs or playlists.
"""

from __future__ import annotations

import time

from ytmusicapi import YTMusic

from . import candidates, llm
from .catalog import Catalog, CatalogPlaylist, get_catalog
from .models import (
    ListeningContext,
    MixPlan,
    MusicTarget,
    PlannedTrack,
    PlanRequest,
    PlanResponse,
    PlaylistPicks,
    SourcePlaylist,
    Usage,
)

SHORTLIST_SIZE = 150  # playlists shown to the LLM after narrowing the ~3,400-item catalogue
POOL_FOR_ORDERING = 40  # top-scored songs the LLM orders into the final mix

TARGET_SYSTEM = """You are Melodi, the music brain of a personal music app. Read the listener's moment and decide what it calls for.

How to weigh the signals:
- A written description is the strongest signal, then the mood they tapped.
- Weather, time of day and activity shape energy and warmth (rain or late night: softer; sunny morning or a workout: brighter).
- The listener's own languages and favourite artists outweigh the local language of the city they're in.

Choose categories only from this list, copied exactly:
{categories}

Include a language or regional category when the listener's languages call for it (Telugu, Hindi, Tamil, Kannada, Malayalam, Punjabi -> "Bollywood & Indian"; Korean -> "K-Pop"; Spanish -> "Latin").
Keywords are words likely to appear in fitting playlist titles, such as an industry name ("Tollywood", "Kollywood"), a language, an era or a style."""

PICK_SYSTEM = """You are Melodi, choosing which curated YouTube Music playlists to draw a mix from.
Pick 3-6 playlists from the numbered list whose songs best fit the target. Favour playlists in the listener's languages, and mix one or two mood playlists with language-specific ones when that fits. Use only numbers shown in the list."""

ORDER_SYSTEM = """You are Melodi, sequencing a personal mix from numbered candidate songs.
- Use exactly {size} different candidates, only numbers from the list.
- Shape the energy to suit the moment: ease in, keep transitions smooth, no jarring jumps.
- Avoid the same artist twice in a row. Where they fit, favour the listener's favourite artists.
- Title: at most 6 words, evocative, no emoji. Description: one sentence linking the mix to the moment.
- For each song, "why" is under 12 words and specific (artist, feel, or how it fits the moment)."""


def plan(request: PlanRequest) -> PlanResponse:
    started = time.monotonic()
    ctx = request.context
    usage = Usage(model=llm.MODEL)
    catalog = get_catalog(ctx.country_code or "")
    categories = sorted({p.category for p in catalog.playlists})

    # 1. Understand the moment.
    target = llm.ask(
        TARGET_SYSTEM.format(categories="\n".join(f"- {c}" for c in categories)),
        describe(ctx),
        MusicTarget,
        usage,
    )
    target = clean_target(target, categories)

    # 2. Narrow the catalogue in code, then let the LLM pick from the shortlist.
    shortlist = narrow(catalog, target)
    picks = llm.ask(
        PICK_SYSTEM,
        f"{describe(ctx)}\n\nTarget: {target.model_dump_json()}\n\nPlaylists:\n{numbered(shortlist)}",
        PlaylistPicks,
        usage,
    )
    chosen = valid_picks(picks.numbers, shortlist) or shortlist[:3]

    # 3. Real songs from those playlists, scored and trimmed without the LLM.
    yt = YTMusic(location=catalog.location)
    pool = candidates.collect(yt, chosen, ctx.taste)
    ranked = candidates.rank(pool, ctx.taste, keep=POOL_FOR_ORDERING)
    size = min(request.size, len(ranked))

    # 4. The LLM orders the mix and explains it.
    mix = llm.ask(
        ORDER_SYSTEM.format(size=size),
        f"{describe(ctx)}\n\nTarget: {target.summary}\n\nCandidates:\n{candidate_lines(ranked)}",
        MixPlan,
        usage,
    )
    tracks = assemble(mix, ranked, size)

    usage.seconds = round(time.monotonic() - started, 2)
    return PlanResponse(
        title=mix.title.strip() or target.summary,
        description=mix.description.strip(),
        target=target,
        sources=[SourcePlaylist(playlist_id=p.playlist_id, title=p.title, category=p.category) for p in chosen],
        tracks=tracks,
        usage=usage,
    )


def describe(ctx: ListeningContext) -> str:
    taste = ctx.taste
    lines = [
        f"Local time: {ctx.local_time}" + (f" ({ctx.daypart})" if ctx.daypart else ""),
        f"Weather: {ctx.weather}" if ctx.weather else None,
        f"Activity: {ctx.activity}" if ctx.activity else None,
        f"Place: {ctx.city}" if ctx.city else None,
        f"Mood they tapped: {ctx.mood}" if ctx.mood else None,
        f'They asked for: "{ctx.description}"' if ctx.description else None,
        f"Favourite artists: {', '.join(taste.top_artists)}" if taste.top_artists else None,
        f"Languages they listen in: {', '.join(taste.languages)}" if taste.languages else None,
    ]
    return "The listener's moment:\n" + "\n".join(f"- {line}" for line in lines if line)


def clean_target(target: MusicTarget, categories: list[str]) -> MusicTarget:
    known = {c.casefold(): c for c in categories}
    return target.model_copy(
        update={
            "categories": [known[c.casefold()] for c in target.categories if c.casefold() in known],
            "keywords": [k.strip() for k in target.keywords if len(k.strip()) >= 3][:12],
            "energy": min(max(target.energy, 0.0), 1.0),
            "valence": min(max(target.valence, 0.0), 1.0),
        }
    )


def narrow(catalog: Catalog, target: MusicTarget) -> list[CatalogPlaylist]:
    """Keyword matches first (they carry language/region), then the chosen categories."""
    keywords = [k.casefold() for k in target.keywords + target.languages]
    chosen = set(target.categories)

    def keyword_hits(p: CatalogPlaylist) -> int:
        text = f"{p.title} {p.shelf}".casefold()
        return sum(k in text for k in keywords)

    matches = [(keyword_hits(p), p.category in chosen, p) for p in catalog.playlists]
    matches = [m for m in matches if m[0] or m[1]]
    matches.sort(key=lambda m: (-m[0], not m[1], m[2].number))
    return [p for _, _, p in matches[:SHORTLIST_SIZE]] or catalog.playlists[:SHORTLIST_SIZE]


def numbered(playlists: list[CatalogPlaylist]) -> str:
    return "\n".join(f"{p.number}. {p.title} [{p.category} > {p.shelf}]" for p in playlists)


def valid_picks(numbers: list[int], shortlist: list[CatalogPlaylist]) -> list[CatalogPlaylist]:
    allowed = {p.number: p for p in shortlist}
    picked: list[CatalogPlaylist] = []
    for n in numbers:
        if n in allowed and allowed[n] not in picked:
            picked.append(allowed[n])
    return picked[:6]


def candidate_lines(ranked: list[candidates.Candidate]) -> str:
    return "\n".join(
        f"{i}. {c.title} - {', '.join(c.artists) or 'Unknown'}" + (" (radio from a song they like)" if c.from_your_radio else "")
        for i, c in enumerate(ranked, start=1)
    )


def assemble(mix: MixPlan, ranked: list[candidates.Candidate], size: int) -> list[PlannedTrack]:
    """Keeps the LLM's order where valid, then tops up from the scores if it returned too few."""
    order: list[tuple[candidates.Candidate, str | None]] = []
    used: set[int] = set()
    for pick in mix.picks:
        if 1 <= pick.number <= len(ranked) and pick.number not in used:
            used.add(pick.number)
            order.append((ranked[pick.number - 1], pick.why.strip() or None))
    for i, c in enumerate(ranked, start=1):
        if len(order) >= size:
            break
        if i not in used:
            order.append((c, None))
    return [
        PlannedTrack(
            video_id=c.video_id,
            title=c.title,
            artists=c.artists,
            album=c.album,
            duration_seconds=c.duration_seconds,
            thumbnail=c.thumbnail,
            why=why,
        )
        for c, why in order[:size]
    ]
