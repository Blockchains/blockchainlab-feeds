# blockchainlab-feeds

Public data feeds for [blockchainlab.com](https://blockchainlab.com) (Blockchain Lab). Contains **only** public X post IDs, links,
author handles, short trimmed summaries and engagement counts, plus public hackathon listings. No secrets, no private data.

| Feed | Path | Raw URL |
|---|---|---|
| X intel (24h, clustered) | `feeds/x-intel/latest.json`, `feeds/x-intel/YYYY-MM-DD.json` | https://raw.githubusercontent.com/Blockchains/blockchainlab-feeds/main/feeds/x-intel/latest.json |
| Mentions of Blockchain Lab | `feeds/mentions/latest.json` | https://raw.githubusercontent.com/Blockchains/blockchainlab-feeds/main/feeds/mentions/latest.json |
| Hackathons / grants / bounties | `feeds/hackathons/latest.json` | https://raw.githubusercontent.com/Blockchains/blockchainlab-feeds/main/feeds/hackathons/latest.json |
| Briefing drafts (review before publishing) | `feeds/briefings-drafts/*.md` | |
| Run status | `feeds/status/last-run.json` | |

Topics: Ethereum, Bitcoin, Hedera, L2s, DeFi, Regulation, AI x crypto (+ Other). Watchlist: `watchlist.json`.

## Pipeline

The X source is an MCP connector, so it cannot run from cron. A daily routine agent:

1. `python3 scripts/fetch_plan.py --date $(date +%F)` → list of MCP calls (server `user-X`).
2. Runs each call via the connector and saves `{"name","tool","args","fetched_at","response"}` to
   `/workspace/pulse-port/x-intel/raw/<date>/<name>.json` (errors saved too).
3. `bash scripts/run_daily.sh <date>` → `build_feeds.py` (clusters, mentions, hackathons from Devpost + ETHGlobal,
   0-3 briefing drafts, digest HTML/text outside the repo) → gitleaks → commit → push.

Schema notes: unknown counts are `null` (e.g. when X is unavailable), never `0`. `x_status` is `ok` or `unavailable`.
Summaries are trimmed from the post's own text; nothing is invented.
