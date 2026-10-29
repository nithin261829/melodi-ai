"""Lite evals: rule-based checks over recorded mixes. No LLM judge.

    uv run python -m evals.run --record        # make real mixes for every scenario (spends API credit), then check
    uv run python -m evals.run                 # re-check the saved mixes in evals/results.json (free)
    uv run python -m evals.run --record --modes pipeline --only sad-night-telugu
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from app import agent, planner  # noqa: E402  (after .env, so the model settings apply)
from app.candidates import song_key  # noqa: E402
from app.models import ListeningContext, PlanRequest, PlanResponse  # noqa: E402

HERE = Path(__file__).parent
SCENARIOS = HERE / "scenarios.json"
RESULTS = HERE / "results.json"
REPORT = HERE / "REPORT.md"
SIZE = 15

# USD per million tokens (input, output), for the models Melodi may run on.
PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0)}


def check(result: dict, expect: dict, size: int) -> dict[str, bool]:
    """Every rule is a plain, deterministic check on one mix."""
    tracks = result["tracks"]
    leads = [(t["artists"] or ["?"])[0].casefold() for t in tracks]
    words = len(result["title"].split())
    sources = result["sources"]
    checks = {
        "right size": len(tracks) == size,
        "no duplicate songs": len({song_key(t["title"]) for t in tracks}) == len(tracks),
        "reason for ≥90% of songs": sum(bool(t.get("why")) for t in tracks) >= 0.9 * len(tracks),
        "≤3 songs per artist": all(leads.count(a) <= 3 for a in set(leads)),
        "no artist twice in a row": all(a != b for a, b in zip(leads, leads[1:])),
        "title 1-6 words": 1 <= words <= 6,
        "no fallback": not result.get("fallback_reason"),
    }
    if expect.get("categories"):
        checks["mood fits"] = any(s["category"] in expect["categories"] for s in sources)
    if expect.get("language_words"):
        words_ = [w.casefold() for w in expect["language_words"]]
        checks["language fits"] = any(any(w in s["title"].casefold() for w in words_) for s in sources)
    return checks


def record(scenarios: list[dict], modes: list[str], saved: dict) -> dict:
    for sc in scenarios:
        for mode in modes:
            request = PlanRequest(context=ListeningContext(**sc["context"]), size=SIZE, mode=mode)
            started = time.monotonic()
            try:
                response: PlanResponse = agent.plan(request) if mode == "agent" else planner.plan(request)
                saved[f"{sc['id']}|{mode}"] = json.loads(response.model_dump_json())
                print(f"recorded {sc['id']:28} {mode:8} {time.monotonic() - started:5.1f}s")
            except Exception as e:  # keep going; a failed scenario is reported, not fatal
                saved[f"{sc['id']}|{mode}"] = {"error": f"{type(e).__name__}: {e}"}
                print(f"FAILED   {sc['id']:28} {mode:8} {e}")
    RESULTS.write_text(json.dumps(saved, indent=1, ensure_ascii=False))
    return saved


def report(scenarios: list[dict], modes: list[str], saved: dict) -> str:
    lines = ["# Lite eval report", "", f"Rule-based checks on recorded mixes ({SIZE} songs each). No LLM judge. Re-run free with `uv run python -m evals.run`.", ""]
    header = "| Scenario | " + " | ".join(f"{m} checks" for m in modes) + " |"
    lines += [header, "|---|" + "---|" * len(modes)]
    totals = {m: {"passed": 0, "checks": 0, "cost": 0.0, "seconds": 0.0, "runs": 0, "failed": []} for m in modes}
    for sc in scenarios:
        row = [f"`{sc['id']}`"]
        for m in modes:
            r = saved.get(f"{sc['id']}|{m}")
            if not r:
                row.append("not recorded")
                continue
            if "error" in r:
                row.append("❌ error")
                totals[m]["failed"].append(f"{sc['id']}: {r['error']}")
                continue
            c = check(r, sc["expect"], SIZE)
            ok = sum(c.values())
            t = totals[m]
            t["passed"] += ok
            t["checks"] += len(c)
            t["runs"] += 1
            u = r["usage"]
            pin, pout = PRICES.get(u["model"], (0, 0))
            t["cost"] += u["input_tokens"] * pin / 1e6 + u["output_tokens"] * pout / 1e6
            t["seconds"] += u["seconds"]
            failed = [name for name, passed in c.items() if not passed]
            t["failed"] += [f"{sc['id']}: {name}" for name in failed]
            row.append(f"{'✅' if not failed else '⚠️'} {ok}/{len(c)}")
        lines.append("| " + " | ".join(row) + " |")
    lines += ["", "| | " + " | ".join(modes) + " |", "|---|" + "---|" * len(modes)]
    lines.append("| Checks passed | " + " | ".join(f"{t['passed']}/{t['checks']} ({100 * t['passed'] / max(t['checks'], 1):.0f}%)" for t in totals.values()) + " |")
    lines.append("| Avg cost per mix | " + " | ".join(f"${t['cost'] / max(t['runs'], 1):.4f}" for t in totals.values()) + " |")
    lines.append("| Avg time per mix | " + " | ".join(f"{t['seconds'] / max(t['runs'], 1):.1f} s" for t in totals.values()) + " |")
    lines.append("| Total cost of this run | " + " | ".join(f"${t['cost']:.3f}" for t in totals.values()) + " |")
    for m, t in totals.items():
        if t["failed"]:
            lines += ["", f"**{m}: failed checks**", ""] + [f"- {f}" for f in t["failed"]]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--record", action="store_true", help="make real mixes first (spends API credit)")
    parser.add_argument("--modes", default="pipeline,agent", help="comma-separated: pipeline, agent")
    parser.add_argument("--only", help="run a single scenario id")
    args = parser.parse_args()

    scenarios = json.loads(SCENARIOS.read_text())
    if args.only:
        scenarios = [s for s in scenarios if s["id"] == args.only]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    saved = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    if args.record:
        saved = record(scenarios, modes, saved)
    text = report(json.loads(SCENARIOS.read_text()) if not args.only else scenarios, modes, saved)
    if not args.only:
        REPORT.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
