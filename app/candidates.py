"""Turns chosen playlists into a pool of real songs, then scores and trims it without the LLM."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from ytmusicapi import YTMusic

from .catalog import CatalogPlaylist
from .models import Taste

PLAYLIST_LIMIT = 100
RADIO_LIMIT = 40
MAX_RADIO_SEEDS = 2
MAX_PER_ARTIST = 3
MAX_SECONDS = 10 * 60


@dataclass
class Candidate:
    video_id: str
    title: str
    artists: list[str]
    album: str | None
    duration_seconds: int | None
    thumbnail: str | None
    playlists: set[str] = field(default_factory=set)  # which curated playlists it appeared in
    best_position: int = PLAYLIST_LIMIT  # earliest position across those playlists
    from_your_radio: bool = False
    score: float = 0.0


def collect(yt: YTMusic, picks: list[CatalogPlaylist], taste: Taste) -> dict[str, Candidate]:
    """Songs from the curated playlists, plus radio seeded by liked songs that fit the mood."""
    pool: dict[str, Candidate] = {}

    with ThreadPoolExecutor(max_workers=6) as pool_exec:
        playlists = list(pool_exec.map(lambda p: _safe(lambda: yt.get_playlist(p.playlist_id, limit=PLAYLIST_LIMIT)), picks))
    for pick, playlist in zip(picks, playlists):
        for position, track in enumerate((playlist or {}).get("tracks", [])):
            candidate = _add(pool, track)
            if candidate:
                candidate.playlists.add(pick.playlist_id)
                candidate.best_position = min(candidate.best_position, position)

    # A liked song that also sits in today's curated lists is a seed that fits both mood and taste.
    liked = set(taste.liked_video_ids)
    seeds = [vid for vid, c in sorted(pool.items(), key=lambda kv: kv[1].best_position) if vid in liked][:MAX_RADIO_SEEDS]
    with ThreadPoolExecutor(max_workers=MAX_RADIO_SEEDS or 1) as pool_exec:
        radios = list(pool_exec.map(lambda v: _safe(lambda: yt.get_watch_playlist(videoId=v, radio=True, limit=RADIO_LIMIT)), seeds))
    for radio in radios:
        for track in (radio or {}).get("tracks", [])[1:]:  # first item is the seed itself
            candidate = _add(pool, track)
            if candidate:
                candidate.from_your_radio = True
    return pool


def rank(pool: dict[str, Candidate], taste: Taste, keep: int) -> list[Candidate]:
    """Scores every candidate and returns the best `keep`, with recent plays and artist floods removed."""
    recent = set(taste.recent_video_ids)
    favourite_artists = {a.casefold() for a in taste.top_artists}

    scored: list[Candidate] = []
    for candidate in pool.values():
        if candidate.video_id in recent:
            continue
        if candidate.duration_seconds and candidate.duration_seconds > MAX_SECONDS:
            continue
        mood_fit = 2.0 * len(candidate.playlists)  # several curated lists agreeing is a strong signal
        prominence = 0.5 * (1 - candidate.best_position / PLAYLIST_LIMIT)  # editors put standouts first
        taste_fit = 1.5 if any(a.casefold() in favourite_artists for a in candidate.artists) else 0.0
        radio_fit = 1.0 if candidate.from_your_radio else 0.0
        candidate.score = mood_fit + prominence + taste_fit + radio_fit
        scored.append(candidate)

    scored.sort(key=lambda c: (-c.score, c.video_id))  # tie-break on ID so results are reproducible
    per_artist: dict[str, int] = {}
    kept: list[Candidate] = []
    for candidate in scored:
        lead = (candidate.artists[0] if candidate.artists else "").casefold()
        if per_artist.get(lead, 0) >= MAX_PER_ARTIST:
            continue
        per_artist[lead] = per_artist.get(lead, 0) + 1
        kept.append(candidate)
        if len(kept) == keep:
            break
    return kept


def _add(pool: dict[str, Candidate], track: dict) -> Candidate | None:
    video_id = track.get("videoId")
    if not video_id or track.get("isAvailable") is False:
        return None
    if video_id not in pool:
        thumbs = track.get("thumbnails") or track.get("thumbnail") or []
        album = track.get("album")
        pool[video_id] = Candidate(
            video_id=video_id,
            title=track.get("title") or "",
            artists=[a["name"] for a in track.get("artists") or [] if a.get("name")],
            album=album.get("name") if isinstance(album, dict) else None,
            duration_seconds=track.get("duration_seconds") or _seconds(track.get("length") or track.get("duration")),
            thumbnail=thumbs[-1]["url"] if thumbs else None,
        )
    return pool[video_id]


def _seconds(text: str | None) -> int | None:
    if not text:
        return None
    try:
        total = 0
        for part in text.split(":"):
            total = total * 60 + int(part)
        return total
    except ValueError:
        return None


def _safe(load):
    """One unavailable playlist or radio shouldn't sink the whole mix."""
    try:
        return load()
    except Exception:  # ytmusicapi raises a mix of KeyError/HTTP errors on odd pages
        return None
