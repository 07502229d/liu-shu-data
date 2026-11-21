#!/usr/bin/env python3
"""Nightly updater for the liu-shu-data repo.

1. Refresh draws.json via the liu-shu-web pipeline (on.cc API + trim/patch).
2. Rebuild next_draw.json: try HKJC official GraphQL (verbatim allowlisted
   marksixResult operation); if unreachable, roll the schedule forward
   (Tue/Thu/Sat, close 21:15 HKT) with estimated prize left null (apps render
   null as —; never fabricate a figure).
Run from anywhere; paths are absolute. Import to GitHub is the caller's job.
"""
import gzip, json, os, subprocess, sys, urllib.request
from datetime import date, timedelta

WEB = "/home/hatch/workspace/liu-shu-web"
HERE = "/home/hatch/workspace/liu-shu-data-repo"

def refresh_draws():
    subprocess.run([sys.executable, "scripts/fetch_data.py"], cwd=WEB, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([sys.executable, "scripts/trim_data.py"], cwd=WEB, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    src = os.path.join(WEB, "site/data/draws.json")
    dst = os.path.join(HERE, "draws.json")
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    return data

FRAGMENT = ("fragment lotteryDrawsFragment on LotteryDraw {\n    id\n    year\n"
    "    no\n    openDate\n    closeDate\n    drawDate\n    status\n"
    "    snowballCode\n    snowballName_en\n    snowballName_ch\n"
    "    lotteryPool {\n      sell\n      status\n      totalInvestment\n"
    "      jackpot\n      unitBet\n      estimatedPrize\n"
    "      derivedFirstPrizeDiv\n      lotteryPrizes {\n        type\n"
    "        winningUnit\n        dividend\n      }\n    }\n"
    "    drawResult {\n      drawnNo\n      xDrawnNo\n    }\n  }")
QUERY = ("\n        " + FRAGMENT + "\n        query marksixResult("
    "$lastNDraw: Int, $startDate: String, $endDate: String, "
    "$drawType: LotteryDrawType) {\n            lotteryDraws("
    "lastNDraw: $lastNDraw, startDate: $startDate, endDate: $endDate, "
    "drawType: $drawType) {\n              ...lotteryDrawsFragment\n"
    "            }\n        }\n    ")

def num(v):
    try:
        return int(float(v))
    except Exception:
        return 0

def try_graphql():
    body = {"operationName": "marksixResult", "query": QUERY,
            "variables": {"lastNDraw": 3, "drawType": "All"}}
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"https": proxy, "http": proxy}))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(
        "https://info.cld.hkjc.com/graphql/base/",
        data=json.dumps(body).encode(),
        headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json",
                 "Origin": "https://bet.hkjc.com",
                 "Referer": "https://bet.hkjc.com/en/marksix/results"})
    with opener.open(req, timeout=45) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        data = json.loads(raw.decode("utf-8"))
    draws = (data.get("data") or {}).get("lotteryDraws") or []
    nxt = next((d for d in draws if d.get("status") == "Defined"), None)
    if not nxt:
        return None
    pool = nxt.get("lotteryPool") or {}
    est = num(pool.get("estimatedPrize")) or num(pool.get("derivedFirstPrizeDiv")) or num(pool.get("jackpot"))
    y, no = int(nxt["year"]), int(nxt["no"])
    return {
        "draw_no": f"{y % 100:02d}/{no:03d}",
        "date": str(nxt["drawDate"])[:10],
        "close_at": nxt.get("closeDate"),
        "est_first_prize": est or None,
        "jackpot": num(pool.get("jackpot")),
        "snowball_name": nxt.get("snowballName_ch") or "",
        "turnover": num(pool.get("totalInvestment")),
        "source": "HKJC official GraphQL (marksixResult), fetched by liu-shu-data nightly updater.",
    }

def schedule_fallback(draws_data):
    last = draws_data["draws"][-1]
    yy, seq = (int(x) for x in last["id"].split("/"))
    year = 2000 + yy
    d = date.fromisoformat(last["date"])
    # draw days: Tue(1) Thu(3) Sat(5)
    delta = 1
    while (d + timedelta(days=delta)).weekday() not in (1, 3, 5):
        delta += 1
    nd = d + timedelta(days=delta)
    if nd.year != year:
        year, seq = nd.year, 0
    return {
        "draw_no": f"{year % 100:02d}/{seq + 1:03d}",
        "date": nd.isoformat(),
        "close_at": f"{nd.isoformat()}T21:15:00+08:00",
        "est_first_prize": None,
        "jackpot": 0,
        "snowball_name": "",
        "turnover": 0,
        "source": "Schedule roll-forward (Tue/Thu/Sat, close 21:15 HKT); HKJC GraphQL unreachable at fetch time, estimated prize not available (shown as —).",
    }

def keep_existing_next(draws_data):
    """Preserve a manually verified next_draw.json when GraphQL is unreachable
    (e.g. a snowball draw moved off the Tue/Thu/Sat grid, so the roll-forward
    fallback would name a cancelled date). Keep it only if it names the
    immediate next draw after the latest result and its date has not passed."""
    try:
        with open(os.path.join(HERE, "next_draw.json"), encoding="utf-8") as f:
            cur = json.load(f)
        last = draws_data["draws"][-1]
        yy, seq = (int(x) for x in last["id"].split("/"))
        if cur.get("draw_no") != f"{yy:02d}/{seq + 1:03d}":
            return None
        if date.fromisoformat(cur["date"]) < date.today():
            return None
        if "Kept by nightly updater" not in cur.get("source", ""):
            cur["source"] = (cur.get("source", "") +
                " [Kept by nightly updater: GraphQL unreachable; entry matches next draw and is still upcoming.]").strip()
        return cur
    except Exception:
        return None

def main():
    draws = refresh_draws()
    try:
        nxt = try_graphql()
    except Exception as e:
        print(f"graphql failed: {type(e).__name__} {str(e)[:120]}", file=sys.stderr)
        nxt = None
    if nxt is None:
        nxt = keep_existing_next(draws) or schedule_fallback(draws)
    with open(os.path.join(HERE, "next_draw.json"), "w", encoding="utf-8") as f:
        json.dump(nxt, f, ensure_ascii=False, indent=2)
    print(f"draws: {draws['meta']['count']} to {draws['meta']['latest']}; next: {nxt['draw_no']} {nxt['date']} est={nxt['est_first_prize']}")

if __name__ == "__main__":
    main()
