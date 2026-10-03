#!/usr/bin/env python3
"""Print the exact X MCP calls a routine agent must make for one daily run.

The X connector is an MCP tool (user-X), so it cannot be called from cron/python.
A routine agent runs this script, performs every call in the printed plan via the
MCP connector, and saves each raw response to:

    <raw_dir>/<date>/<name>.json  =  {"name","tool","args","fetched_at","response"}

`response` is the connector's raw output (JSON object, or the raw string if it was
not JSON). Errors must be saved too (same envelope) so the build can report them.
Then run scripts/build_feeds.py.
"""
import argparse, json, datetime as dt, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
POST_FIELDS = "created_at,public_metrics,author_id,entities,lang,conversation_id"
USER_FIELDS = "username,name,verified,public_metrics"


def plan(date: str, now: dt.datetime | None = None):
    wl = json.loads((ROOT / "watchlist.json").read_text())
    lim = wl["limits"]
    now = now or dt.datetime.now(dt.timezone.utc)
    start = (now - dt.timedelta(hours=24)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    # end_time must be >=10s before now for the X API
    end = (now - dt.timedelta(seconds=30)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    calls = [{"name": "00-usage", "tool": "get_usage_credits", "args": {}}]
    handles = [a["handle"] for a in wl["accounts"]]
    calls.append({"name": "01-verify-users", "tool": "get_users_by_usernames",
                  "args": {"usernames": ",".join(handles), "user.fields": "public_metrics,verified,description,created_at"}})
    n = lim["watchlist_chunk"]
    for i in range(0, len(handles), n):
        chunk = handles[i:i + n]
        q = "(" + " OR ".join(f"from:{h}" for h in chunk) + ") -is:retweet"
        calls.append({"name": f"10-watchlist-{i // n:02d}", "tool": "search_posts_all",
                      "args": {"query": q, "start_time": start, "end_time": end, "max_results": lim["max_results_watchlist"],
                               "sort_order": "relevancy", "post.fields": POST_FIELDS, "expansions": "author_id", "user.fields": USER_FIELDS}})
    for slug, q in wl["topics"].items():
        calls.append({"name": f"20-topic-{slug}", "tool": "search_posts_all",
                      "args": {"query": q, "start_time": start, "end_time": end, "max_results": lim["max_results_per_topic"],
                               "sort_order": "relevancy", "post.fields": POST_FIELDS, "expansions": "author_id", "user.fields": USER_FIELDS}})
    calls.append({"name": "30-mentions", "tool": "search_posts_all",
                  "args": {"query": wl["mentions_query"], "start_time": start, "end_time": end, "max_results": lim["max_results_mentions"],
                           "sort_order": "recency", "post.fields": POST_FIELDS, "expansions": "author_id", "user.fields": USER_FIELDS}})
    calls.append({"name": "40-news", "tool": "search_news", "args": {"query": "crypto blockchain", "max_age_hours": 24, "max_results": 10}})
    calls.append({"name": "99-usage-after", "tool": "get_usage_credits", "args": {}})
    return {"date": date, "window": {"start_time": start, "end_time": end}, "server": "user-X", "calls": calls}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat())
    a = ap.parse_args()
    print(json.dumps(plan(a.date), indent=2))
