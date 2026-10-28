"""Request/response shapes for the API, and the structured outputs Claude must return."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ---- What the phone sends -------------------------------------------------------------------


class Taste(BaseModel):
    """Worked out on the phone from the local library; never stored on the server."""

    top_artists: list[str] = Field(default_factory=list, max_length=20)
    languages: list[str] = Field(default_factory=list, max_length=6)
    liked_video_ids: list[str] = Field(default_factory=list, max_length=200)
    recent_video_ids: list[str] = Field(default_factory=list, max_length=200)


class ListeningContext(BaseModel):
    """Only coarse labels; the phone never sends GPS coordinates."""

    local_time: str = Field(description="ISO 8601 with offset, e.g. 2026-10-28T21:40:00-04:00")
    daypart: str | None = Field(None, description='e.g. "early morning", "golden hour", "late night"')
    weather: str | None = Field(None, description='e.g. "light rain, 24°C"')
    activity: Literal["still", "walking", "driving"] | None = None
    city: str | None = None
    country_code: str | None = Field(None, description="ISO 3166 alpha-2; picks the regional catalogue")
    mood: str | None = Field(None, description='A mood chip the listener tapped, e.g. "calm"')
    description: str | None = Field(None, max_length=300, description="Free text: what they want to hear")
    taste: Taste = Field(default_factory=Taste)


class PlanRequest(BaseModel):
    context: ListeningContext
    size: int = Field(25, ge=10, le=50)


# ---- Structured outputs from Claude ---------------------------------------------------------
# Plain types only: the server enforces JSON-schema shape, the code below enforces ranges/IDs.


class MusicTarget(BaseModel):
    """Step 1: what this moment calls for."""

    summary: str = Field(description="One short line describing the moment, e.g. 'Rainy night drive, calm'")
    categories: list[str] = Field(description="2-5 category names copied exactly from the list given")
    keywords: list[str] = Field(description="Words likely to appear in fitting playlist titles, e.g. 'Tollywood', 'Telugu', 'Lo-Fi'")
    languages: list[str]
    energy: float = Field(description="0 = very calm, 1 = very energetic")
    valence: float = Field(description="0 = sad/dark, 1 = happy/bright")


class PlaylistPicks(BaseModel):
    """Step 2: which curated playlists to draw songs from."""

    numbers: list[int] = Field(description="3-6 playlist numbers from the list given")


class OrderedPick(BaseModel):
    number: int = Field(description="Candidate number from the list given")
    why: str = Field(description="Under 12 words, specific to this listener and moment")


class MixPlan(BaseModel):
    """Step 3: the final running order, title and blurb."""

    title: str = Field(description="Short, evocative mix title")
    description: str = Field(description="One sentence that ties the mix to the moment")
    picks: list[OrderedPick]


# ---- What the phone gets back ---------------------------------------------------------------


class PlannedTrack(BaseModel):
    video_id: str
    title: str
    artists: list[str]
    album: str | None = None
    duration_seconds: int | None = None
    thumbnail: str | None = None
    why: str | None = None


class SourcePlaylist(BaseModel):
    playlist_id: str
    title: str
    category: str


class Usage(BaseModel):
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    llm_calls: int = 0
    seconds: float = 0


class PlanResponse(BaseModel):
    title: str
    description: str
    target: MusicTarget
    sources: list[SourcePlaylist]
    tracks: list[PlannedTrack]
    usage: Usage
