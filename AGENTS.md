# AGENTS.md: blockchainlab-feeds

Instructions for AI coding agents (Grok, Cursor, Claude Code, Codex, Copilot and others) working **in** this repo or **using it as a building block**. Humans: see [README.md](README.md).

## What this is

Public JSON feeds for blockchainlab.com: hackathons/grants/bounties, events, clustered X intel and mentions (public post IDs, links, handles, short trimmed summaries, counts only), built daily.

- Kind: dataset, automation · stability: `beta` · licence: NOASSERTION
- Machine-readable manifest: [`blocks.json`](blocks.json) (schema: [BLOCKS-SCHEMA](https://github.com/Blockchains/.github/blob/main/docs/BLOCKS-SCHEMA.md))
- How it fits with the other Blockchains repos: [Build with Blocks](https://github.com/Blockchains/.github/blob/main/docs/BUILD-WITH-BLOCKS.md)

## Setup

```bash
python3 --version
```

## Build and test

```bash
python3 scripts/fetch_plan.py --date $(date +%F)
python3 scripts/build_feeds.py --date $(date +%F) --raw-dir /tmp/raw --digest-dir /tmp/digest   # local build, no push
```

Tests hit **live** public networks/APIs (the org rule is no mocks). A failure can be an upstream outage: re-run before changing code.

## Structure

| Path | What |
|---|---|
| `feeds/<feed>/latest.json` | current feed (+ dated copies) |
| `scripts/fetch_plan.py` | list of X MCP calls to make |
| `scripts/build_feeds.py` | builds all feeds |
| `scripts/run_daily.sh` | build → gitleaks → commit → push |
| `watchlist.json` | accounts/topics |

## Conventions

- Public data only; summaries are trimmed from the post text, nothing invented.
- No licence file yet.

## Extension points

- New feed: add a builder in `scripts/build_feeds.py` writing `feeds/<name>/latest.json`.

## Do

- Keep `x_status` honest (`unavailable` when X could not be read).

## Don't

- Store private data or full post text.
- Invent data, mock network responses in shipped code, or hard-code values that should come from the live source; every repo here is 'no mocks, real data'.
- Commit secrets, keys or `.env` files. Run `gitleaks` before pushing; CI and the org policy reject leaks.

## Using it from another project

- **feeds/hackathons/latest.json** (http): `items[]: title, url, dates, prize, location, organizer, themes, state, source, verified`
- **feeds/events/latest.json** (http): `https://raw.githubusercontent.com/Blockchains/blockchainlab-feeds/main/feeds/events/latest.json`
- **feeds/x-intel/latest.json** (http): `https://raw.githubusercontent.com/Blockchains/blockchainlab-feeds/main/feeds/x-intel/latest.json`
- **scripts/build_feeds.py** (cli): `python3 scripts/build_feeds.py --date YYYY-MM-DD --raw-dir DIR --digest-dir DIR`

See the README section [Use as a building block](README.md#use-as-a-building-block) for a copy-paste example.

## Related blocks

- [Blockchains/blockchainlab-api](https://github.com/Blockchains/blockchainlab-api): republishes hackathons and events as API datasets
- [Blockchains/blockchains.github.io](https://github.com/Blockchains/blockchains.github.io): powers /events
- [Blockchains/hackathons](https://github.com/Blockchains/hackathons): human tracker of the same events
