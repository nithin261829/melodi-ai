"""Agent mode: Claude plans the mix by calling the tools in app/tools.py itself.

The loop is written by hand (not the SDK's beta tool runner) so it can cap the number of rounds,
record every tool call for the response's `trace`, and fall back to the pipeline on any failure.
"""

from __future__ import annotations

import time

from ytmusicapi import YTMusic

from . import llm, planner, tools
from .catalog import get_catalog
from .models import PlanRequest, PlanResponse, SourcePlaylist, ToolCall, Usage

MAX_ROUNDS = 10

SYSTEM = """You are Melodi, an AI DJ. Build a mix of real songs for the listener's moment using your tools.

How to work:
1. Decide what the moment calls for. A written description is the strongest signal, then the mood they tapped. Weather, time of day and activity shape the energy. Their favourite artists show their languages and taste, and outweigh the local language of their city.
2. search_catalog for fitting curated playlists. Mix one or two mood playlists with ones in the listener's languages. If the results don't fit, search again with other words.
3. get_playlist_tracks for the 3-6 best playlists.
4. rank_candidates. Optionally get_radio for one or two candidates that capture the vibe, then rank again.
5. finish_mix with exactly {size} different candidates in playing order: ease in, keep transitions smooth, avoid the same artist twice in a row. Title at most 6 words. Each reason under 12 words.

Category names for search_catalog:
{categories}

Be efficient: use few rounds, and call independent tools together."""


def plan(request: PlanRequest) -> PlanResponse:
    started = time.monotonic()
    ctx = request.context
    usage = Usage(model=llm.MODEL)
    catalog = get_catalog(ctx.country_code or "")
    box = tools.Toolbox(catalog, YTMusic(location=catalog.location), ctx.taste)
    categories = sorted({p.category for p in catalog.playlists})
    system = SYSTEM.format(size=request.size, categories="\n".join(f"- {c}" for c in categories))
    messages: list = [{"role": "user", "content": planner.describe(ctx)}]
    trace: list[ToolCall] = []

    for _ in range(MAX_ROUNDS):
        response = llm.turn(system, messages, tools.DEFINITIONS, usage)
        messages.append({"role": "assistant", "content": response.content})
        calls = [b for b in response.content if b.type == "tool_use"]
        if not calls:
            if response.stop_reason == "max_tokens":
                raise AgentFailed("Ran out of output tokens")
            # Claude replied without a tool; remind it once how to finish.
            messages.append({"role": "user", "content": "Please submit the mix with the finish_mix tool."})
            continue

        results = []
        for call in calls:  # all results go back in one message, as the API expects
            t0 = time.monotonic()
            try:
                output, is_error = box.run(call.name, call.input), False
            except (tools.ToolError, TypeError, ValueError) as e:
                output, is_error = f"Error: {e}", True
            trace.append(ToolCall(tool=call.name, input=tools.compact(call.input), result=tools.result_preview(output), ms=int((time.monotonic() - t0) * 1000)))
            results.append({"type": "tool_result", "tool_use_id": call.id, "content": output, "is_error": is_error})
        messages.append({"role": "user", "content": results})

        if box.mix:
            break
    else:
        raise AgentFailed(f"No finish_mix after {MAX_ROUNDS} rounds")

    if not box.mix:
        raise AgentFailed("Agent stopped without a mix")
    size = min(request.size, len(box.ranked))
    usage.seconds = round(time.monotonic() - started, 2)
    return PlanResponse(
        title=box.mix.title.strip(),
        description=box.mix.description.strip(),
        sources=[SourcePlaylist(playlist_id=p.playlist_id, title=p.title, category=p.category) for p in box.loaded],
        tracks=planner.assemble(box.mix, box.ranked, size),
        usage=usage,
        mode="agent",
        trace=trace,
    )


class AgentFailed(RuntimeError):
    pass
