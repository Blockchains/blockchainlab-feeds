# blockchainlab-feeds

Public data feeds for [blockchainlab.com](https://blockchainlab.com) (Blockchain Lab). Contains **only** public X post IDs, links,
author handles, short trimmed summaries and engagement counts, plus public hackathon listings. No secrets, no private data.

| Feed | Path | Raw URL |
|---|---|---|
| X intel (24h, clustered) | `feeds/x-intel/latest.json`, `feeds/x-intel/YYYY-MM-DD.json` | https://raw.githubusercontent.com/Blockchains/blockchainlab-feeds/main/feeds/x-intel/latest.json |
| Mentions of Blockchain Lab | `feeds/mentions/latest.json` | https://raw.githubusercontent.com/Blockchains/blockchainlab-feeds/main/feeds/mentions/latest.json |
| Hackathons / grants / bounties | `feeds/hackathons/latest.json` | https://raw.githubusercontent.com/Blockchains/blockchainlab-feeds/main/feeds/hackathons/latest.json |
| Briefing drafts (review before publishing) | `feeds/briefings-drafts/*.md` | |
| Events (hackathons + summits) | `feeds/events/latest.json` | https://raw.githubusercontent.com/Blockchains/blockchainlab-feeds/main/feeds/events/latest.json |
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

Live: the feeds are served as raw JSON (table above) and power [blockchains.github.io/events](https://blockchains.github.io/events/) and the [Open Data API](https://blockchains.github.io/blockchainlab-api/).

## Usage

```bash
python3 scripts/fetch_plan.py --date 2026-10-04                       # list the X MCP calls to make
python3 scripts/build_feeds.py --date 2026-10-04 \
  --raw-dir /workspace/pulse-port/x-intel/raw --digest-dir /tmp/digest  # build feeds locally (no push)
```

Example: `curl -s https://raw.githubusercontent.com/Blockchains/blockchainlab-feeds/main/feeds/hackathons/latest.json`

## Configuration

| Setting | Default | Purpose |
|---|---|---|
| `RAW` (run_daily.sh) / `--raw-dir` | `/workspace/pulse-port/x-intel/raw` | Saved raw X MCP responses |
| `OUT` (run_daily.sh) / `--digest-dir` | `/workspace/pulse-port/x-intel` | Digest HTML/text and alerts (not committed) |
| `watchlist.json` | — | Accounts and topics to track |

`run_daily.sh` runs gitleaks before committing and pushing.

## Licence

No licence file has been added yet. Feeds contain only public post IDs, links and short excerpts; rights in the underlying posts stay with their authors.

## Contributing

Issues and pull requests are welcome. Please read the [contributing guide](https://github.com/Blockchains/.github/blob/main/CONTRIBUTING.md), [code of conduct](https://github.com/Blockchains/.github/blob/main/CODE_OF_CONDUCT.md) and [security policy](https://github.com/Blockchains/.github/blob/main/SECURITY.md) first.

---
Built by Blockchain Lab — [blockchainlab.com](https://blockchainlab.com/?utm_source=github&utm_medium=readme&utm_campaign=blockchainlab-feeds)
