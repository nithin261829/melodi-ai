"""YouTube Music's curated "Moods & genres" playlists: the fixed menu Melodi picks from.

Each playlist is chosen by YouTube's editors and labelled by the category and shelf it sits under
(e.g. "Sad › Bollywood sad"), so picking from this list is far more reliable than free-text search.
The catalogue changes rarely, so it is cached per country for a day.
"""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from ytmusicapi import YTMusic

CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
TTL_SECONDS = 24 * 60 * 60


class CatalogPlaylist(BaseModel):
    number: int  # short handle the LLM uses instead of the long playlist ID
    playlist_id: str
    title: str
    category: str  # e.g. "Chill", "Bollywood & Indian"
    shelf: str  # e.g. "Coffee shop blends", "Bollywood sad"


class Catalog(BaseModel):
    location: str
    fetched_at: float
    playlists: list[CatalogPlaylist]

    def by_number(self) -> dict[int, CatalogPlaylist]:
        return {p.number: p for p in self.playlists}

    def as_prompt(self) -> str:
        """One line per playlist, grouped by category; stable order so the prompt cache hits."""
        lines: list[str] = []
        current = None
        for p in self.playlists:
            if p.category != current:
                current = p.category
                lines.append(f"\n## {current}")
            shelf = f" ({p.shelf})" if p.shelf and p.shelf != p.title else ""
            lines.append(f"{p.number}. {p.title}{shelf}")
        return "\n".join(lines).strip()


_lock = threading.Lock()
_memory: dict[str, Catalog] = {}


def get_catalog(location: str = "") -> Catalog:
    """The catalogue for a country (ISO 3166 alpha-2, e.g. "IN"; "" = YouTube's default)."""
    location = location.upper()
    with _lock:
        cached = _memory.get(location) or _read_disk(location)
        if cached and time.time() - cached.fetched_at < TTL_SECONDS:
            _memory[location] = cached
            return cached
        fresh = _fetch(location)
        _memory[location] = fresh
        _write_disk(fresh)
        return fresh


def _fetch(location: str) -> Catalog:
    yt = YTMusic(location=location)
    categories = [c for group in yt.get_mood_categories().values() for c in group]

    # ytmusicapi's own get_mood_playlists crashes on pages that mix song shelves with
    # playlists (e.g. "Bollywood & Indian"), so read the raw page and keep only playlists.
    def load(cat: dict[str, str]) -> list[tuple[str, str, str, str]]:
        page = yt._send_request("browse", {"browseId": "FEmusic_moods_and_genres_category", "params": cat["params"]})
        return [(cat["title"], shelf, pid, title) for shelf, pid, title in _playlists_in(page)]

    with ThreadPoolExecutor(max_workers=8) as pool:
        per_category = list(pool.map(load, categories))

    seen: set[str] = set()
    playlists: list[CatalogPlaylist] = []
    for rows in per_category:
        for category, shelf, pid, title in rows:
            if pid in seen:
                continue
            seen.add(pid)
            playlists.append(
                CatalogPlaylist(number=len(playlists) + 1, playlist_id=pid, title=title, category=category, shelf=shelf)
            )
    return Catalog(location=location, fetched_at=time.time(), playlists=playlists)


def _playlists_in(node: Any, shelf: str = "") -> list[tuple[str, str, str]]:
    """Walks a browse response and returns (shelf title, playlist id, playlist title)."""
    found: list[tuple[str, str, str]] = []
    if isinstance(node, dict):
        for header_key in ("musicCarouselShelfBasicHeaderRenderer", "gridHeaderRenderer"):
            header = node.get("header", {}).get(header_key)
            if header:
                shelf = _text(header.get("title")) or shelf
        item = node.get("musicTwoRowItemRenderer")
        if item:
            browse_id = (
                item.get("title", {}).get("runs", [{}])[0].get("navigationEndpoint", {}).get("browseEndpoint", {}).get("browseId", "")
            )
            if browse_id.startswith("VL"):
                found.append((shelf, browse_id[2:], _text(item.get("title"))))
            return found
        for value in node.values():
            found.extend(_playlists_in(value, shelf))
    elif isinstance(node, list):
        for value in node:
            found.extend(_playlists_in(value, shelf))
    return found


def _text(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return "".join(run.get("text", "") for run in value.get("runs", []))


def _path(location: str) -> Path:
    return CACHE_DIR / f"catalog-{location or 'default'}.json"


def _read_disk(location: str) -> Catalog | None:
    try:
        return Catalog.model_validate_json(_path(location).read_text())
    except (OSError, ValueError):
        return None


def _write_disk(catalog: Catalog) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    _path(catalog.location).write_text(json.dumps(catalog.model_dump()))
