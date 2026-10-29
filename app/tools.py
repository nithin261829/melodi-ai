"""The agent's tools: one JSON definition per tool, plus the code that runs it.

Claude only ever sees numbers the tools handed out (playlist numbers, candidate numbers), and every
tool checks them, so the agent can explore freely but cannot invent playlists or songs.
"""

from __future__ import annotations

import json

from ytmusicapi import YTMusic

from . import candidates
from .catalog import Catalog, CatalogPlaylist
from .models import MixPlan, MusicTarget, OrderedPick, Taste

MAX_PLAYLISTS = 8  # total playlists the agent may load per mix
RANK_DEFAULT, RANK_MAX = 40, 60

# ---- Tool definitions (what Claude sees) ---------------------------------------------------
# `strict: true` makes the API guarantee inputs match the schema exactly.

SEARCH_CATALOG = {
    "name": "search_catalog",
    "description": (
        "Search YouTube Music's curated Moods & genres playlists (about 3,400, chosen by human editors). "
        "Returns up to 60 numbered playlists with their category and shelf. Use the numbers with get_playlist_tracks. "
        "Search again with different words if the results don't fit the listener's mood or languages."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "categories": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Category names from the list in your instructions, e.g. 'Sad', 'Chill', 'Bollywood & Indian'",
            },
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Words to look for in playlist titles, e.g. 'Tollywood', 'Telugu', 'heartbreak', 'lo-fi'",
            },
        },
        "required": ["categories", "keywords"],
        "additionalProperties": False,
    },
}

GET_PLAYLIST_TRACKS = {
    "name": "get_playlist_tracks",
    "description": (
        f"Load the real songs from playlists returned by search_catalog into the candidate pool. "
        f"At most {MAX_PLAYLISTS} playlists in total per mix. Returns how many songs each playlist added."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "playlist_numbers": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Playlist numbers exactly as shown by search_catalog",
            },
        },
        "required": ["playlist_numbers"],
        "additionalProperties": False,
    },
}

GET_RADIO = {
    "name": "get_radio",
    "description": (
        "Add YouTube's radio (similar songs) for one candidate song to the pool. Use it to go deeper on a song "
        "that captures the vibe well, especially one by the listener's favourite artists. Call rank_candidates first "
        "so you have candidate numbers."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "candidate_number": {"type": "integer", "description": "A candidate number from the latest rank_candidates result"},
        },
        "required": ["candidate_number"],
        "additionalProperties": False,
    },
}

RANK_CANDIDATES = {
    "name": "rank_candidates",
    "description": (
        "Score every song in the pool and return the best ones, numbered. Scoring rewards songs that several "
        "chosen playlists agree on, the listener's favourite artists and radio; it merges duplicate uploads, "
        "drops recently played songs and allows at most 3 songs per artist."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": f"How many to return, {RANK_DEFAULT} is a good default (max {RANK_MAX})"},
        },
        "required": ["limit"],
        "additionalProperties": False,
    },
}

FINISH_MIX = {
    "name": "finish_mix",
    "description": (
        "Submit the final mix. Call this exactly once, at the end. Picks are candidate numbers from the latest "
        "rank_candidates result, in playing order, each with a short reason."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Short, evocative mix title, at most 6 words, no emoji"},
            "description": {"type": "string", "description": "One sentence linking the mix to the moment"},
            "picks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "number": {"type": "integer", "description": "Candidate number"},
                        "why": {"type": "string", "description": "Under 12 words, specific to this listener and moment"},
                    },
                    "required": ["number", "why"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["title", "description", "picks"],
        "additionalProperties": False,
    },
}

DEFINITIONS = [SEARCH_CATALOG, GET_PLAYLIST_TRACKS, GET_RADIO, RANK_CANDIDATES, FINISH_MIX]


# ---- Tool implementations (what runs when Claude calls one) ---------------------------------


class ToolError(ValueError):
    """Reported back to Claude as an error result so it can correct itself."""


class Toolbox:
    """Holds one request's state: what the agent has searched, loaded and ranked so far."""

    def __init__(self, catalog: Catalog, yt: YTMusic, taste: Taste):
        self.catalog = catalog
        self.yt = yt
        self.taste = taste
        self.seen: dict[int, CatalogPlaylist] = {}  # playlist numbers handed to the agent
        self.loaded: list[CatalogPlaylist] = []
        self.pool: dict[str, candidates.Candidate] = {}
        self.ranked: list[candidates.Candidate] = []
        self.mix: MixPlan | None = None

    def run(self, name: str, tool_input: dict) -> str:
        handler = {
            "search_catalog": self.search_catalog,
            "get_playlist_tracks": self.get_playlist_tracks,
            "get_radio": self.get_radio,
            "rank_candidates": self.rank_candidates,
            "finish_mix": self.finish_mix,
        }.get(name)
        if handler is None:
            raise ToolError(f"Unknown tool {name!r}")
        return handler(**tool_input)

    def search_catalog(self, categories: list[str], keywords: list[str]) -> str:
        from .planner import narrow  # shared with the pipeline; imported here to avoid a cycle

        known = {p.category.casefold(): p.category for p in self.catalog.playlists}
        target = MusicTarget(
            summary="",
            categories=[known[c.casefold()] for c in categories if c.casefold() in known],
            keywords=[k for k in keywords if len(k.strip()) >= 3],
            languages=[],
            energy=0.5,
            valence=0.5,
        )
        if not target.categories and not target.keywords:
            raise ToolError("Give at least one known category or a keyword of 3+ letters.")
        found = narrow(self.catalog, target)[:60]
        self.seen.update({p.number: p for p in found})
        lines = [f"{p.number}. {p.title} [{p.category} > {p.shelf}]" for p in found]
        return f"{len(found)} playlists:\n" + "\n".join(lines)

    def get_playlist_tracks(self, playlist_numbers: list[int]) -> str:
        picks = []
        for n in playlist_numbers:
            p = self.seen.get(n)
            if p is None:
                raise ToolError(f"Playlist {n} wasn't returned by search_catalog. Use numbers from a search result.")
            if p not in self.loaded and p not in picks:
                picks.append(p)
        room = MAX_PLAYLISTS - len(self.loaded)
        if room <= 0:
            raise ToolError(f"Already loaded {MAX_PLAYLISTS} playlists, the maximum. Rank and finish.")
        picks = picks[:room]
        counts = candidates.add_playlists(self.yt, self.pool, picks)
        self.loaded.extend(picks)
        lines = [f"{p.title}: {counts.get(p.playlist_id, 0)} songs" for p in picks]
        return f"Pool now has {len(self.pool)} songs.\n" + "\n".join(lines)

    def get_radio(self, candidate_number: int) -> str:
        if not 1 <= candidate_number <= len(self.ranked):
            raise ToolError("Use a candidate number from the latest rank_candidates result.")
        seed = self.ranked[candidate_number - 1]
        added = candidates.add_radio(self.yt, self.pool, [seed.video_id])
        return f"Radio for '{seed.title}' added {added} new songs. Pool now has {len(self.pool)} songs. Rank again to see them."

    def rank_candidates(self, limit: int) -> str:
        if not self.pool:
            raise ToolError("The pool is empty. Load playlists with get_playlist_tracks first.")
        self.ranked = candidates.rank(self.pool, self.taste, keep=max(5, min(limit, RANK_MAX)))
        lines = [
            f"{i}. {c.title} - {', '.join(c.artists) or 'Unknown'}"
            f" (in {len(c.playlists)} playlist{'s' if len(c.playlists) != 1 else ''}{', radio' if c.from_your_radio else ''})"
            for i, c in enumerate(self.ranked, start=1)
        ]
        return f"Top {len(self.ranked)} of {len(self.pool)} songs:\n" + "\n".join(lines)

    def finish_mix(self, title: str, description: str, picks: list[dict]) -> str:
        if not self.ranked:
            raise ToolError("Call rank_candidates before finish_mix.")
        valid = [p for p in picks if 1 <= int(p["number"]) <= len(self.ranked)]
        if len(valid) < max(5, len(picks) // 2):
            raise ToolError("Most picks weren't candidate numbers from the latest rank_candidates result.")
        self.mix = MixPlan(title=title, description=description, picks=[OrderedPick(**p) for p in valid])
        return "Mix accepted."


def result_preview(text: str) -> str:
    return text.splitlines()[0][:160] if text else ""


def compact(tool_input: dict) -> dict:
    """Trace-friendly copy of a tool input (finish_mix picks can be long)."""
    if "picks" in tool_input:
        return {**tool_input, "picks": f"{len(tool_input['picks'])} picks"}
    return json.loads(json.dumps(tool_input))
