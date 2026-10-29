# Lite eval report

Rule-based checks on recorded mixes (15 songs each). No LLM judge. Re-run free with `uv run python -m evals.run`.

| Scenario | pipeline checks | agent checks |
|---|---|---|
| `rainy-night-drive-telugu` | ✅ 9/9 | ✅ 9/9 |
| `sad-night-telugu` | ✅ 9/9 | ✅ 9/9 |
| `gym-hype-english` | ✅ 8/8 | ✅ 8/8 |
| `focus-study` | ✅ 8/8 | ✅ 8/8 |
| `fall-asleep` | ✅ 8/8 | ✅ 8/8 |
| `romantic-evening-hindi` | ✅ 9/9 | ✅ 9/9 |
| `tamil-house-party` | ✅ 9/9 | ✅ 9/9 |
| `kpop-morning-walk` | ✅ 9/9 | ✅ 9/9 |
| `punjabi-road-trip` | ✅ 9/9 | ✅ 9/9 |
| `sunny-morning-english` | ✅ 8/8 | ✅ 8/8 |
| `new-user-no-signals` | ✅ 7/7 | ✅ 7/7 |
| `description-beats-weather` | ✅ 9/9 | ✅ 9/9 |

| | pipeline | agent |
|---|---|---|
| Checks passed | 102/102 (100%) | 102/102 (100%) |
| Avg cost per mix | $0.0014 | $0.0030 |
| Avg time per mix | 11.7 s | 14.0 s |
| Total cost of this run | $0.017 | $0.036 |
