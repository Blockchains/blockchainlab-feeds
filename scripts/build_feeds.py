#!/usr/bin/env python3
"""Build blockchainlab-feeds from raw X MCP responses + public web hackathon sources.

Usage:
  python3 scripts/build_feeds.py --date 2026-10-03 \
      --raw-dir /workspace/pulse-port/x-intel/raw \
      --digest-dir /workspace/pulse-port/x-intel

Writes (repo-relative):
  feeds/x-intel/<date>.json, feeds/x-intel/latest.json
  feeds/mentions/latest.json, feeds/mentions/seen.json
  feeds/hackathons/latest.json, feeds/hackathons/seen.json
  feeds/briefings-drafts/<date>-*.md  (0-3 drafts)
  feeds/status/last-run.json, feeds/status/watchlist-verification.json
And outside the repo (not committed): <digest-dir>/digest-<date>.html/.txt,
  <digest-dir>/alerts-<date>.json (new mentions).

Rules: only public post ids/urls/authors/short summaries. Summaries are trimmed
from the post text itself - nothing is invented. Unknown counts are null, not 0.
"""
import argparse, datetime as dt, html, json, pathlib, re, sys, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 blockchainlab-feeds"
TOPIC_LABELS = {"ethereum": "Ethereum", "bitcoin": "Bitcoin", "hedera": "Hedera", "l2": "L2s", "defi": "DeFi",
                "regulation": "Regulation", "ai_crypto": "AI x crypto", "other": "Other"}
KEYWORDS = [
    ("hedera", r"\b(hedera|hashgraph|hbar|hashpack|hcs)\b"),
    ("l2", r"\b(rollup|layer ?2|l2s?|arbitrum|optimism|op stack|superchain|base chain|zksync|starknet|polygon|scroll|linea|l2beat)\b"),
    ("ai_crypto", r"\b(ai agents?|agentic|x402|onchain agents?|llm|autonomous agents?)\b"),
    ("regulation", r"\b(mica|fca|sec\b|cftc|esma|regulat\w*|stablecoin bill|genius act|clarity act|lawmakers?|congress|enforcement)\b"),
    ("defi", r"\b(defi|tvl|stablecoins?|usdc|usdt|lending|dex|amm|liquid staking|restaking|rwa|tokeni[sz]ed|yield)\b"),
    ("bitcoin", r"\b(bitcoin|btc|lightning|satoshi|bip-?\d+|ordinals|taproot)\b"),
    ("ethereum", r"\b(ethereum|eth\b|eip-?\d+|pectra|fusaka|glamsterdam|validators?|vitalik|solidity|evm)\b"),
]
HACK_RE = re.compile(r"\b(hackathon|bounty|bounties|grants? (round|program)|buildathon)\b", re.I)


def now_utc():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def load_json(p, default):
    try:
        return json.loads(pathlib.Path(p).read_text())
    except Exception:
        return default


def write_json(p, obj):
    p = pathlib.Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def http_get(url, accept="application/json", timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


# ---------------------------------------------------------------- raw X data
def parse_response(resp):
    if isinstance(resp, str):
        try:
            resp = json.loads(resp)
        except Exception:
            return None, {"error": "non-json response", "sample": resp[:200]}
    if isinstance(resp, list) and resp and isinstance(resp[0], dict) and "text" in resp[0] and isinstance(resp[0]["text"], str):
        # MCP content blocks
        try:
            resp = json.loads(resp[0]["text"])
        except Exception:
            return None, {"error": "unparseable content block"}
    if not isinstance(resp, dict):
        return None, {"error": "unexpected response type"}
    if "data" not in resp and ("title" in resp or "errors" in resp or "detail" in resp):
        return None, {"error": resp.get("title") or "error", "reason": resp.get("reason"), "detail": (resp.get("detail") or "")[:240]}
    return resp, None


def load_raw(raw_dir: pathlib.Path):
    calls, errors = {}, []
    for f in sorted(raw_dir.glob("*.json")):
        env = load_json(f, None)
        if not env:
            errors.append({"call": f.stem, "error": "unreadable file"})
            continue
        resp, err = parse_response(env.get("response"))
        if err:
            errors.append({"call": env.get("name", f.stem), "tool": env.get("tool"), **err})
        calls[env.get("name", f.stem)] = {"env": env, "resp": resp}
    return calls, errors


def summarize(text: str, n=160):
    t = re.sub(r"https?://\S+", "", text or "")
    t = re.sub(r"\s+", " ", t).strip()
    m = re.match(r"(.+?[.!?])(\s|$)", t)
    s = m.group(1) if m and len(m.group(1)) >= 40 else t
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"


def classify(text, hint=None, author_topic=None):
    low = (text or "").lower()
    for topic, rx in KEYWORDS:
        if re.search(rx, low):
            return topic
    if hint in TOPIC_LABELS:
        return hint
    if author_topic in TOPIC_LABELS:
        return author_topic
    return "other"


def engagement(pm):
    pm = pm or {}
    keys = ["like_count", "retweet_count", "reply_count", "quote_count", "bookmark_count", "impression_count"]
    e = {k.replace("_count", ""): pm.get(k) for k in keys if k in pm}
    e["score"] = (pm.get("like_count") or 0) + 2 * (pm.get("retweet_count") or 0) + (pm.get("reply_count") or 0) + 2 * (pm.get("quote_count") or 0)
    return e


def collect_posts(calls, wl):
    author_topic = {a["handle"].lower(): a["topic"] for a in wl["accounts"]}
    posts = {}
    for name, c in calls.items():
        r = c["resp"]
        if not r or not isinstance(r.get("data"), list):
            continue
        users = {u["id"]: u for u in (r.get("includes") or {}).get("users", [])}
        hint = name.split("20-topic-", 1)[1] if name.startswith("20-topic-") else None
        for p in r["data"]:
            if "id" not in p:
                continue
            u = users.get(p.get("author_id"), {})
            handle = u.get("username") or ""
            url = p.get("url") or (f"https://x.com/{handle}/status/{p['id']}" if handle else f"https://x.com/i/status/{p['id']}")
            urls = [x.get("expanded_url") or x.get("url") for x in ((p.get("entities") or {}).get("urls") or [])]
            rec = posts.get(p["id"]) or {
                "id": p["id"], "url": url, "author": handle or None, "author_name": u.get("name"),
                "time": p.get("created_at"), "text_len": len(p.get("text", "")),
                "summary": summarize(p.get("text", "")), "engagement": engagement(p.get("public_metrics")),
                "links": [x for x in urls if x][:5], "sources": [],
                "_text": p.get("text", ""),
            }
            rec["sources"].append(name)
            if hint == "hackathons":
                rec["hackathon_lead"] = True
            rec["topic"] = rec.get("topic") or classify(p.get("text", ""), hint if hint != "hackathons" else None, author_topic.get(handle.lower()))
            posts[p["id"]] = rec
    return posts


# ------------------------------------------------------------ web hackathons
def devpost():
    out, err = [], None
    try:
        for page in (1, 2):
            d = json.loads(http_get(f"https://devpost.com/api/hackathons?themes%5B%5D=Blockchain&status%5B%5D=upcoming&status%5B%5D=open&order_by=recently-added&page={page}"))
            for h in d.get("hackathons", []):
                prize = re.sub(r"<[^>]+>", "", h.get("prize_amount") or "").strip() or None
                out.append({"source": "devpost", "id": f"devpost-{h['id']}", "title": h["title"], "url": h["url"],
                            "organizer": h.get("organization_name"), "dates": h.get("submission_period_dates"),
                            "state": h.get("open_state"), "prize": prize if prize not in ("0", "$0") else None,
                            "location": ((h.get("displayed_location") or {}).get("location") or "").strip(" ,") or None,
                            "registrations": h.get("registrations_count"),
                            "themes": [t["name"] for t in h.get("themes", [])], "verified": "listed on devpost.com API"})
    except Exception as e:
        err = f"devpost: {type(e).__name__}: {e}"[:200]
    return out, err


def ethglobal(today):
    out, err = [], None
    try:
        h = http_get("https://ethglobal.com/events", accept="text/html").replace('\\"', '"')
        seen = set()
        for m in re.finditer(r'\{"id":(\d+),"name":"([^"]+)","slug":"([^"]+)","type":"([^"]+)","medium":"([^"]+)","startTime":"([^"]+)","endTime":"([^"]+)","status":"([^"]+)"', h):
            i, name, slug, typ, medium, st, en, status = m.groups()
            if i in seen or typ != "hackathon" or status in ("past", "finished", "cancelled"):
                continue
            if en[:10] < today:
                continue
            seen.add(i)
            out.append({"source": "ethglobal", "id": f"ethglobal-{i}", "title": name, "url": f"https://ethglobal.com/events/{slug}",
                        "organizer": "ETHGlobal", "dates": f"{st[:10]} to {en[:10]}", "state": status, "prize": None,
                        "location": medium, "themes": ["Ethereum"], "verified": "listed in ethglobal.com/events page data"})
    except Exception as e:
        err = f"ethglobal: {type(e).__name__}: {e}"[:200]
    return out, err


# ------------------------------------------------------------- briefings
def briefing_md(date, title, intro, items, source_note):
    lines = [f"---", f"title: \"{title}\"", f"date: {date}", "status: draft", "generated_by: blockchainlab-feeds/scripts/build_feeds.py",
             "review: required before publishing on blockchainlab.com", "---", "", f"# {title}", "", intro, ""]
    for it in items:
        lines.append(f"- {it}")
    lines += ["", f"_Sources: {source_note} Every claim above is a trimmed quote or listing field from the linked source; "
              "nothing was added. Check each link before publishing._", ""]
    return "\n".join(lines)


def make_briefings(date, clusters, hacks):
    drafts = []
    ranked = sorted(((t, ps) for t, ps in clusters.items() if t != "other" and len(ps) >= 3), key=lambda x: -sum(p["engagement"]["score"] for p in x[1]))
    for topic, ps in ranked[:2]:
        items = [f"[@{p['author']}]({p['url']}): \"{p['summary']}\"" for p in ps[:6]]
        drafts.append((f"{date}-{topic}.md", briefing_md(date, f"{TOPIC_LABELS[topic]}: what builders posted in the last 24 hours ({date})",
                       f"The {len(ps)} most-engaged public X posts on {TOPIC_LABELS[topic]} from the Blockchain Lab watchlist and topic search, quoted as posted.",
                       items, "public X posts (linked).")))
    if len(drafts) < 3 and len(hacks) >= 3:
        items = []
        for h in hacks[:10]:
            bits = [h["dates"] or "dates on page"]
            if h.get("prize"):
                bits.append(f"prizes: {h['prize']}")
            if h.get("location"):
                bits.append(str(h["location"]))
            items.append(f"[{h['title']}]({h['url']}) ({h['source']}): " + "; ".join(bits))
        drafts.append((f"{date}-hackathons.md", briefing_md(date, f"Blockchain hackathons open or upcoming ({date})",
                       "Open and upcoming blockchain hackathons from the Devpost and ETHGlobal public listings, as listed on each platform on the date above.",
                       items, "devpost.com public hackathon API and ethglobal.com/events.")))
    return drafts[:3]


# ------------------------------------------------------------------ digest
def digest(date, xi, mentions, hacks_doc, drafts, status):
    x_ok = status["x"]["status"] == "ok"
    top = xi.get("top", [])[:10]
    new_m = mentions.get("new", [])
    hacks = hacks_doc.get("items", [])
    T = [f"Blockchain Lab X intel digest - {date}", ""]
    H = [f"<html><body style=\"font-family:Arial,sans-serif;max-width:680px;margin:auto;color:#111\">",
         f"<h2>Blockchain Lab X intel digest &middot; {html.escape(date)}</h2>"]
    if not x_ok:
        msg = f"X data unavailable this run: {status['x'].get('error')}. Post, mention and topic counts below are unknown (not zero)."
        T += [msg, ""]
        H.append(f"<p style=\"background:#fff3cd;padding:8px\"><b>X data unavailable.</b> {html.escape(status['x'].get('error') or '')}. Post, mention and topic counts are unknown, not zero.</p>")
    else:
        T += [f"Posts: {xi['counts']['posts']} | New mentions: {len(new_m)} | Hackathons listed: {len(hacks)}", "", "Top posts:"]
        H.append(f"<p>Posts: <b>{xi['counts']['posts']}</b> &middot; New mentions: <b>{len(new_m)}</b> &middot; Hackathons listed: <b>{len(hacks)}</b></p><h3>Top posts</h3><ol>")
        for p in top:
            T.append(f"- [{TOPIC_LABELS.get(p['topic'], p['topic'])}] @{p['author']}: {p['summary']} {p['url']}")
            H.append(f"<li>[{html.escape(TOPIC_LABELS.get(p['topic'], p['topic']))}] <a href=\"{p['url']}\">@{html.escape(p['author'] or '?')}</a>: {html.escape(p['summary'])}</li>")
        H.append("</ol>")
        if new_m:
            T += ["", "NEW MENTIONS:"] + [f"- @{m['author']}: {m['summary']} {m['url']}" for m in new_m]
            H.append("<h3>New mentions of Blockchain Lab</h3><ul>" + "".join(f"<li><a href=\"{m['url']}\">@{html.escape(m['author'] or '?')}</a>: {html.escape(m['summary'])}</li>" for m in new_m) + "</ul>")
    T += ["", f"Hackathons (open/upcoming, verified on platform listings): {len(hacks)}"]
    H.append(f"<h3>Hackathons open/upcoming ({len(hacks)})</h3><ul>")
    for h in hacks[:12]:
        extra = f" - prizes {h['prize']}" if h.get("prize") else ""
        T.append(f"- {h['title']} ({h['source']}) {h['dates']}{extra} {h['url']}")
        H.append(f"<li><a href=\"{h['url']}\">{html.escape(h['title'])}</a> ({h['source']}) {html.escape(str(h['dates']))}{html.escape(extra)}</li>")
    H.append("</ul>")
    if drafts:
        T += ["", "Briefing drafts (review before publishing):"] + [f"- https://github.com/Blockchains/blockchainlab-feeds/blob/main/feeds/briefings-drafts/{n}" for n, _ in drafts]
        H.append("<h3>Briefing drafts</h3><ul>" + "".join(f"<li><a href=\"https://github.com/Blockchains/blockchainlab-feeds/blob/main/feeds/briefings-drafts/{n}\">{n}</a></li>" for n, _ in drafts) + "</ul>")
    errs = status.get("web_errors") or []
    if errs:
        T += ["", "Source errors: " + "; ".join(errs)]
        H.append("<p style=\"color:#666\">Source errors: " + html.escape("; ".join(errs)) + "</p>")
    T += ["", "Feeds: https://github.com/Blockchains/blockchainlab-feeds/tree/main/feeds"]
    H.append("<p style=\"color:#666;font-size:12px\">Feeds: <a href=\"https://github.com/Blockchains/blockchainlab-feeds/tree/main/feeds\">github.com/Blockchains/blockchainlab-feeds</a>. Generated automatically; summaries are trimmed post text.</p></body></html>")
    return "\n".join(H), "\n".join(T)


# -------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--raw-dir", default="/workspace/pulse-port/x-intel/raw")
    ap.add_argument("--digest-dir", default="/workspace/pulse-port/x-intel")
    ap.add_argument("--no-web", action="store_true")
    a = ap.parse_args()
    date, gen = a.date, now_utc().isoformat().replace("+00:00", "Z")
    wl = load_json(ROOT / "watchlist.json", {})
    calls, x_errors = load_raw(pathlib.Path(a.raw_dir) / date)
    ok_calls = [n for n, c in calls.items() if c["resp"] is not None]
    if not calls:
        xstat = {"status": "unavailable", "error": "no raw files for this date"}
    elif not ok_calls:
        e = x_errors[0] if x_errors else {}
        xstat = {"status": "unavailable", "error": f"{e.get('error')} ({e.get('reason')})", "errors": x_errors}
    else:
        xstat = {"status": "ok" if not x_errors else "partial", "ok_calls": len(ok_calls), "errors": x_errors}
    if xstat["status"] == "partial":
        xstat["status"] = "ok"
    usage = {k: calls[k]["resp"] for k in ("00-usage", "99-usage-after") if k in calls and calls[k]["resp"]}

    # watchlist verification
    ver = {"date": date, "status": "not_checked", "found": [], "missing": []}
    vr = calls.get("01-verify-users", {}).get("resp")
    if vr and isinstance(vr.get("data"), list):
        found = {u["username"].lower(): u for u in vr["data"]}
        ver = {"date": date, "status": "checked",
               "found": [{"handle": u["username"], "id": u["id"], "followers": (u.get("public_metrics") or {}).get("followers_count")} for u in vr["data"]],
               "missing": [h["handle"] for h in wl["accounts"] if h["handle"].lower() not in found]}
    elif "01-verify-users" in calls:
        ver["status"] = "error"
    write_json(ROOT / "feeds/status/watchlist-verification.json", ver)

    posts = collect_posts(calls, wl) if xstat["status"] == "ok" else {}
    clusters = {t: [] for t in TOPIC_LABELS}
    for p in posts.values():
        clusters.setdefault(p["topic"], []).append(p)
    for t in clusters:
        clusters[t].sort(key=lambda p: -p["engagement"]["score"])
    pub = lambda p: {k: v for k, v in p.items() if not k.startswith("_")}
    top = sorted(posts.values(), key=lambda p: -p["engagement"]["score"])[:20]
    xi = {"date": date, "generated_at": gen, "source": "X API via MCP connector (user-X)", "x_status": xstat["status"],
          "x_error": xstat.get("error"), "window_hours": 24,
          "counts": {"posts": len(posts) if xstat["status"] == "ok" else None,
                     "by_topic": {t: (len(v) if xstat["status"] == "ok" else None) for t, v in clusters.items()}},
          "top": [pub(p) for p in top],
          "clusters": {t: {"label": TOPIC_LABELS[t], "posts": [pub(p) for p in v[:25]]} for t, v in clusters.items()}}
    write_json(ROOT / f"feeds/x-intel/{date}.json", xi)
    write_json(ROOT / "feeds/x-intel/latest.json", xi)

    # mentions
    seen_m = set(load_json(ROOT / "feeds/mentions/seen.json", []))
    ment = []
    if xstat["status"] == "ok":
        for p in posts.values():
            txt = (p["_text"] + " " + " ".join(p["links"])).lower()
            if "30-mentions" in p["sources"] or "blockchainlab.com" in txt or "blockchain lab" in txt or "@blockchainlab" in txt:
                if (p["author"] or "").lower() != "blockchainlab":
                    ment.append(pub(p))
    new_m = [m for m in ment if m["id"] not in seen_m]
    mentions = {"date": date, "generated_at": gen, "x_status": xstat["status"], "x_error": xstat.get("error"),
                "query": wl.get("mentions_query"), "count": len(ment) if xstat["status"] == "ok" else None,
                "new_count": len(new_m) if xstat["status"] == "ok" else None, "items": ment, "new": new_m}
    write_json(ROOT / "feeds/mentions/latest.json", mentions)
    write_json(ROOT / "feeds/mentions/seen.json", sorted(seen_m | {m["id"] for m in ment}))

    # hackathons
    web_errors, hacks = [], []
    if not a.no_web:
        for fn in (lambda: devpost(), lambda: ethglobal(date)):
            items, err = fn()
            hacks += items
            if err:
                web_errors.append(err)
    seen_h = load_json(ROOT / "feeds/hackathons/seen.json", {})
    baseline = not seen_h
    for h in hacks:
        h["first_seen"] = seen_h.get(h["id"], date)
        h["new"] = h["first_seen"] == date and not baseline
        seen_h.setdefault(h["id"], date)
    x_leads = [{"id": p["id"], "url": p["url"], "author": p["author"], "summary": p["summary"], "time": p["time"],
                "verified": False, "note": "X post lead - not yet verified on a platform listing"}
               for p in posts.values() if p.get("hackathon_lead") or HACK_RE.search(p["_text"])][:30]
    hacks_doc = {"date": date, "generated_at": gen, "baseline_run": baseline,
                 "sources": ["devpost.com/api/hackathons (theme Blockchain, open+upcoming)", "ethglobal.com/events (future hackathons)", "X posts (leads only)"],
                 "not_covered": ["dorahacks.io (AWS WAF human verification blocks scripted fetch)", "gitcoin (indexer not reachable from the box)"],
                 "errors": web_errors, "count": len(hacks), "new_count": sum(1 for h in hacks if h["new"]),
                 "items": hacks, "x_leads": x_leads if xstat["status"] == "ok" else None}
    write_json(ROOT / "feeds/hackathons/latest.json", hacks_doc)
    write_json(ROOT / "feeds/hackathons/seen.json", seen_h)

    drafts = make_briefings(date, clusters, hacks)
    for name, md in drafts:
        p = ROOT / "feeds/briefings-drafts" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(md)

    status = {"date": date, "generated_at": gen, "x": {k: v for k, v in xstat.items() if k != "errors"}, "x_errors": x_errors,
              "usage": usage or None, "web_errors": web_errors,
              "counts": {"posts": xi["counts"]["posts"], "mentions": mentions["count"], "new_mentions": mentions["new_count"],
                         "hackathons": len(hacks), "briefing_drafts": len(drafts)}}
    write_json(ROOT / "feeds/status/last-run.json", status)

    dd = pathlib.Path(a.digest_dir)
    dd.mkdir(parents=True, exist_ok=True)
    h, t = digest(date, xi, mentions, hacks_doc, drafts, status)
    (dd / f"digest-{date}.html").write_text(h)
    (dd / f"digest-{date}.txt").write_text(t)
    write_json(dd / f"alerts-{date}.json", {"date": date, "new_mentions": new_m, "x_status": xstat["status"]})
    print(json.dumps(status["counts"] | {"x_status": xstat["status"], "drafts": [n for n, _ in drafts]}))


if __name__ == "__main__":
    sys.exit(main())
