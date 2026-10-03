#!/bin/bash
# Build feeds from saved raw X MCP responses + public web, then gitleaks + push.
# Prereq: a routine agent has saved today's raw MCP responses to $RAW/<date>/ (see scripts/fetch_plan.py).
set -euo pipefail
DATE="${1:-$(date +%F)}"
RAW="${RAW:-/workspace/pulse-port/x-intel/raw}"
OUT="${OUT:-/workspace/pulse-port/x-intel}"
cd "$(dirname "$0")/.."
git pull --rebase --quiet origin main || true
python3 scripts/build_feeds.py --date "$DATE" --raw-dir "$RAW" --digest-dir "$OUT"
gitleaks detect --source . --no-banner --redact --exit-code 1
git add -A feeds watchlist.json
if git diff --cached --quiet; then echo "no changes"; exit 0; fi
gitleaks protect --staged --source . --no-banner --redact --exit-code 1
git -c user.name="Blockchains" -c user.email="Blockchains@users.noreply.github.com" commit -q -m "feeds: $DATE daily build"
git push -q origin main
echo "pushed $(git rev-parse --short HEAD)"
