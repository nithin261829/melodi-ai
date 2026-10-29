"""Offline tests for the agent's tools (no network, no LLM)."""

import pytest

from app import tools
from app.candidates import Candidate
from app.catalog import Catalog, CatalogPlaylist
from app.models import Taste


class FakeYT:
    """Stands in for ytmusicapi: every playlist has the same three songs, radio adds two more."""

    def get_playlist(self, playlist_id, limit=100):
        return {"tracks": [{"videoId": f"{playlist_id}-{i}", "title": f"Song {playlist_id}-{i}", "artists": [{"name": f"A{i}"}]} for i in range(3)]}

    def get_watch_playlist(self, videoId, radio=True, limit=40):
        return {"tracks": [{"videoId": videoId, "title": "seed"}] + [{"videoId": f"r{i}", "title": f"Radio {i}", "artists": [{"name": "R"}]} for i in range(2)]}


def make_box() -> tools.Toolbox:
    rows = [("Tollywood Romance", "Romance"), ("Bollywood Heartbreak", "Sad"), ("Beast Mode", "Workout")]
    rows += [(f"Telugu Mix {i}", "Bollywood & Indian") for i in range(10)]
    catalog = Catalog(
        location="IN",
        fetched_at=0,
        playlists=[CatalogPlaylist(number=i, playlist_id=f"PL{i}", title=t, category=c, shelf="") for i, (t, c) in enumerate(rows, 1)],
    )
    return tools.Toolbox(catalog, FakeYT(), Taste())


def test_every_definition_is_a_strict_closed_schema():
    names = [d["name"] for d in tools.DEFINITIONS]
    assert names == ["search_catalog", "get_playlist_tracks", "get_radio", "rank_candidates", "finish_mix"]
    for d in tools.DEFINITIONS:
        schema = d["input_schema"]
        assert d["strict"] is True and d["description"]
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])


def test_search_returns_numbers_the_box_remembers():
    box = make_box()
    out = box.search_catalog(categories=["sad"], keywords=["Tollywood"])
    assert "Tollywood Romance" in out and "Bollywood Heartbreak" in out and "Beast Mode" not in out
    assert set(box.seen) == {1, 2}


def test_search_needs_something_to_search_for():
    with pytest.raises(tools.ToolError):
        make_box().search_catalog(categories=["Not a category"], keywords=["ab"])


def test_cannot_load_a_playlist_the_agent_never_saw():
    box = make_box()
    with pytest.raises(tools.ToolError, match="search_catalog"):
        box.get_playlist_tracks([3])


def test_playlist_limit_is_enforced():
    box = make_box()
    box.search_catalog(categories=["Bollywood & Indian"], keywords=["Telugu"])
    out = box.get_playlist_tracks(list(box.seen))
    assert len(box.loaded) == tools.MAX_PLAYLISTS and f"{tools.MAX_PLAYLISTS * 3} songs" in out
    with pytest.raises(tools.ToolError, match="maximum"):
        box.get_playlist_tracks([next(iter(box.seen))])


def test_rank_and_radio_and_finish_flow():
    box = make_box()
    with pytest.raises(tools.ToolError, match="empty"):
        box.rank_candidates(limit=40)
    box.search_catalog(categories=["Romance"], keywords=[])
    box.get_playlist_tracks([1])
    assert "Top 3 of 3" in box.rank_candidates(limit=40)
    assert "added 2 new songs" in box.get_radio(candidate_number=1)
    with pytest.raises(tools.ToolError):
        box.get_radio(candidate_number=99)
    box.rank_candidates(limit=40)
    picks = [{"number": n, "why": "fits"} for n in range(1, 6)]
    assert box.finish_mix(title="Rainy Night", description="Soft songs.", picks=picks) == "Mix accepted."
    assert box.mix and len(box.mix.picks) == 5


def test_finish_rejects_mostly_invented_numbers():
    box = make_box()
    box.ranked = [Candidate(video_id=str(i), title=str(i), artists=["A"], album=None, duration_seconds=None, thumbnail=None) for i in range(10)]
    with pytest.raises(tools.ToolError):
        box.finish_mix(title="t", description="d", picks=[{"number": 50 + i, "why": "x"} for i in range(8)])


def test_unknown_tool_is_an_error():
    with pytest.raises(tools.ToolError):
        make_box().run("delete_everything", {})
