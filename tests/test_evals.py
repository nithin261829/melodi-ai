"""The lite-eval rules are code too, so they get tests (no network, no LLM)."""

from evals.run import check


def mix(titles_artists, title="Rainy Night Drive", sources=None, fallback=None, why="fits"):
    return {
        "title": title,
        "tracks": [{"title": t, "artists": [a], "why": why} for t, a in titles_artists],
        "sources": sources or [{"title": "Tollywood Romance", "category": "Romance"}],
        "fallback_reason": fallback,
    }


EXPECT = {"categories": ["Romance", "Sad"], "language_words": ["Tollywood", "Telugu"]}


def test_a_good_mix_passes_every_rule():
    result = check(mix([("A", "x"), ("B", "y"), ("C", "x")]), EXPECT, size=3)
    assert all(result.values()), result


def test_each_rule_catches_its_problem():
    bad = mix(
        [("Urike Urike", "x"), ("Urike Urike (Official Video)", "x"), ("C", "x"), ("D", "x")],
        title="A title that is far too long here",
        sources=[{"title": "Beast Mode", "category": "Workout"}],
        fallback="agent failed",
        why="",
    )
    result = check(bad, EXPECT, size=3)
    failed = {name for name, ok in result.items() if not ok}
    assert failed == {
        "right size",
        "no duplicate songs",
        "reason for ≥90% of songs",
        "≤3 songs per artist",
        "no artist twice in a row",
        "title 1-6 words",
        "no fallback",
        "mood fits",
        "language fits",
    }


def test_mood_and_language_are_skipped_when_not_expected():
    result = check(mix([("A", "x")]), {"categories": [], "language_words": []}, size=1)
    assert "mood fits" not in result and "language fits" not in result
