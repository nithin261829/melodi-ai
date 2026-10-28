"""Offline tests for the deterministic parts of the pipeline (no network, no LLM)."""

from app.candidates import Candidate, rank
from app.catalog import Catalog, CatalogPlaylist
from app.models import MixPlan, MusicTarget, OrderedPick, Taste
from app.planner import assemble, clean_target, narrow, valid_picks


def make_catalog() -> Catalog:
    rows = [
        ("Coffee Shop Blend", "Chill", "Coffee shop blends"),
        ("Tollywood Romance", "Bollywood & Indian", "Featured playlists"),
        ("Bollywood Heartbreak", "Sad", "Bollywood sad"),
        ("Beast Mode", "Workout", "Pump up"),
        ("New Music Telugu", "Bollywood & Indian", "Featured playlists"),
    ]
    return Catalog(
        location="IN",
        fetched_at=0,
        playlists=[CatalogPlaylist(number=i, playlist_id=f"PL{i}", title=t, category=c, shelf=s) for i, (t, c, s) in enumerate(rows, 1)],
    )


def make_target(**overrides) -> MusicTarget:
    base = dict(summary="Rainy night drive", categories=["Chill"], keywords=["Tollywood"], languages=["Telugu"], energy=0.3, valence=0.5)
    return MusicTarget(**{**base, **overrides})


def candidate(vid: str, artist: str, playlists: int = 1, position: int = 50, radio: bool = False) -> Candidate:
    return Candidate(
        video_id=vid,
        title=f"Song {vid}",
        artists=[artist],
        album=None,
        duration_seconds=200,
        thumbnail=None,
        playlists={f"PL{i}" for i in range(playlists)},
        best_position=position,
        from_your_radio=radio,
    )


def test_clean_target_drops_unknown_categories_and_clamps():
    target = clean_target(make_target(categories=["chill", "Made Up"], energy=3, valence=-1), ["Chill", "Sad"])
    assert target.categories == ["Chill"]
    assert (target.energy, target.valence) == (1.0, 0.0)


def test_narrow_puts_language_matches_first_and_skips_unrelated():
    shortlist = narrow(make_catalog(), make_target())
    titles = [p.title for p in shortlist]
    assert titles[:2] == ["Tollywood Romance", "New Music Telugu"]
    assert "Coffee Shop Blend" in titles  # chosen category
    assert "Beast Mode" not in titles  # neither category nor keyword


def test_valid_picks_ignores_invented_and_duplicate_numbers():
    shortlist = make_catalog().playlists[:3]
    picked = valid_picks([2, 99, 2, 1], shortlist)
    assert [p.number for p in picked] == [2, 1]


def test_rank_rewards_agreement_and_taste_and_skips_recent():
    pool = {
        "a": candidate("a", "Sid Sriram", playlists=1),
        "b": candidate("b", "Someone", playlists=2),
        "c": candidate("c", "Someone Else", playlists=3),
        "d": candidate("d", "Other", playlists=1, radio=True),
    }
    taste = Taste(top_artists=["sid sriram"], recent_video_ids=["c"])
    ranked = [c.video_id for c in rank(pool, taste, keep=10)]
    assert "c" not in ranked  # played recently
    assert ranked[0] == "b"  # two curated lists agree (4.0) beats favourite artist (2.0 + 1.5)
    assert ranked.index("a") < ranked.index("d")  # favourite artist beats radio


def test_rank_caps_songs_per_artist():
    pool = {str(i): candidate(str(i), "Same Artist") for i in range(6)}
    assert len(rank(pool, Taste(), keep=10)) == 3


def test_assemble_keeps_valid_order_and_tops_up():
    ranked = [candidate(str(i), f"A{i}") for i in range(5)]
    mix = MixPlan(title="t", description="d", picks=[OrderedPick(number=3, why="fits"), OrderedPick(number=42, why="bad"), OrderedPick(number=3, why="dup")])
    tracks = assemble(mix, ranked, size=3)
    assert [t.video_id for t in tracks] == ["2", "0", "1"]
    assert tracks[0].why == "fits" and tracks[1].why is None
