#!/usr/bin/env python3
"""
update_trades.py - build trades.json, the data behind the "Politician Trades" digest in JD's Toolkit.

Only public STOCK Act disclosure data that can be fetched without bot evasion and without keys:
  * U.S. House: the Clerk's public yearly filing index (https://disclosures-clerk.house.gov/public_disc/financial-pdfs/<year>FD.xml)
    plus each Periodic Transaction Report PDF (.../ptr-pdfs/<year>/<DocID>.pdf), read with `pdftotext -layout`
    (poppler-utils). Requests are slow (one per 0.6 s), identify this project in the User-Agent, and only NEW filings are
    downloaded: rows for filings already in trades.json are reused.
  * U.S. Senate: the Senate eFD site only serves results after a click-through agreement in a browser session, so this script does
    not automate it. Senate rows are copied from the community-maintained CC0 dataset LuxAlgo/market-trackers-data (which parses
    eFD), and are labelled with that source and its own freshness date. If that dataset is unreachable, Senate rows are left out.
Capitol Trades, Quiver Quantitative and Unusual Whales are never fetched; the app only links to them.

Output (written to trades.json, docs/trades.json and android/app/src/main/assets/trades.json):
  {"schema":1,"generated":ISO,"windowDays":N,"sources":[...],"note":"...","trades":[{...}]}
Disclosures are filed up to 45 days after a trade, so a recent trade may not appear yet. Not investment advice.

Usage: python3 update_trades.py [--days 120] [--delay 0.6] [--dry-run]
"""
import argparse, datetime as dt, gzip, io, json, os, re, shutil, subprocess, sys, time
import urllib.request, urllib.error
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
UA = "JDsToolkit-digest/1.0 (+https://github.com/geek4945-creator/jds-toolkit; personal, low-volume, public STOCK Act filings)"
HOUSE_BASE = "https://disclosures-clerk.house.gov/public_disc"
LUX_BASE = "https://raw.githubusercontent.com/LuxAlgo/market-trackers-data/main"
OUTPUTS = [os.path.join(HERE, "trades.json"), os.path.join(HERE, "docs/trades.json"),
           os.path.join(HERE, "android/app/src/main/assets/trades.json")]
MAX_ROWS = 4000
NOTE = ("Public STOCK Act disclosures, shown as filed. Filings can be made up to 45 days after a trade, so recent trades may be "
        "missing. Amounts are ranges. Not investment advice; a disclosed trade says nothing about why it was made.")

# House asset-type codes (https://fd.house.gov/reference/asset-type-codes.aspx); "BD" is used for Senate rows that only say "bond".
ASSET_TYPES = {"4K": "401(k)/retirement account", "AB": "Asset-backed security", "BA": "Bank/money market/CD", "BK": "Brokerage account",
    "CO": "Collectible", "CS": "Corporate bond/note", "CT": "Cryptocurrency", "EF": "ETF", "ET": "Exchange traded note", "FU": "Futures",
    "GS": "Government/agency security", "HE": "Hedge/private equity fund", "HN": "Hedge/private equity fund", "IR": "IRA",
    "MA": "Managed account", "MF": "Mutual fund", "OI": "Ownership interest", "OL": "Ownership interest (business)", "OP": "Option",
    "OT": "Other", "PE": "Pension", "PM": "Precious metal", "PS": "Stock (not publicly traded)", "RE": "REIT", "RS": "Restricted stock units",
    "ST": "Stock", "TR": "Trust", "BD": "Bond/note"}
SENATE_TYPES = {"stock": "ST", "option": "OP", "bond": "BD"}

def fetch(url, binary=True, retries=2, timeout=40):
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r: return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 404, 410, 451): raise          # do not hammer; a block or missing file is final
            last = e
        except Exception as e: last = e
        time.sleep(1.5 * (i + 1))
    raise last

# ----------------------------------------------------------------------------- House PTR PDF parsing
HEADER_RE = re.compile(r"^\s*ID\s+Owner\s+Asset\s+Transaction\s+Date\s+Notification")
ROW_RE = re.compile(r"(?P<type>S \(partial\)|P|S|E)\s+(?P<td>\d\d/\d\d/\d{4})\s+(?P<nd>\d\d/\d\d/\d{4})\s+"
                    r"(?P<amt>(?:Spouse/DC\s+)?Over(?:\s+\$[\d,]+)?|\$[\d,]+(?:\s*-\s*(?:\$[\d,]+)?)?)")
MONEY_RE = re.compile(r"\$[\d,]+")
TICKER_RE = re.compile(r"\(([A-Z][A-Z0-9.\-/]{0,9})\)\s*\[[A-Z]{2}\]")
CODE_RE = re.compile(r"\[([A-Z]{2})\]")
SIDES = {"P": "buy", "S": "sell", "S (partial)": "sell (partial)", "E": "exchange"}
OWNERS = {"SP": "spouse", "DC": "dependent child", "JT": "joint"}

def iso(mdy):
    return dt.datetime.strptime(mdy, "%m/%d/%Y").date().isoformat()

def parse_ptr_text(text):
    """-> (rows, expected) where rows are dicts and expected is the number of '[XX]' asset codes seen (sanity check)."""
    lines = text.replace("\x00", " ").split("\n")
    kept, i = [], 0
    while i < len(lines):                       # drop the table header that repeats on every page (3 lines)
        if HEADER_RE.match(lines[i]): i += 3; continue
        kept.append(lines[i]); i += 1
    paras, cur = [], []
    for ln in kept:
        if ln.strip() == "":
            if cur: paras.append(cur); cur = []
        else: cur.append(ln)
    if cur: paras.append(cur)
    rows = []
    entries = []                                 # an entry starts on its transaction row; a page break can glue two entries together
    for p in paras:
        starts = [k for k, ln in enumerate(p) if ROW_RE.search(ln)]
        for n, k in enumerate(starts):
            entries.append(p[k:(starts[n + 1] if n + 1 < len(starts) else len(p))])
    for p in entries:
        k = 0
        m = ROW_RE.search(p[0])
        col = m.start("type")
        asset_lines = []
        for ln in p:
            if re.match(r"^\s*F\s+S\s*:", ln) or re.match(r"^\s*(S\s+O|L|D|C)\s*:", ln): break
            asset_lines.append(ln[:col].rstrip() if len(ln) > col else ln.rstrip())
        asset = " ".join(a.strip() for a in asset_lines if a.strip())
        owner = ""
        om = re.match(r"^(SP|DC|JT)\s+(.*)$", asset)
        if om: owner, asset = OWNERS[om.group(1)], om.group(2)
        amt = m.group("amt").strip()
        amt = re.sub(r"^Spouse/DC\s+", "", amt)   # "Spouse/DC Over $1,000,000" -> "Over $1,000,000"
        if amt.endswith("-") or amt.endswith("Over"):   # amount wrapped onto the next line: "$15,001 -" / "$50,000"
            rest = "\n".join(p[k:])[m.end("amt") - 0:]
            nxt = MONEY_RE.search(rest)
            if not nxt: continue
            amt = (amt + " " + nxt.group(0)) if amt.endswith("Over") else (amt.rstrip(" -") + " - " + nxt.group(0))
        amt = re.sub(r"\s*-\s*", " - ", amt)
        tk = TICKER_RE.search(asset)
        code = CODE_RE.search(asset)
        name = TICKER_RE.sub("", asset); name = CODE_RE.sub("", name)
        name = re.sub(r"\s+", " ", name).strip(" -")
        rows.append({"ticker": tk.group(1) if tk else "", "asset": name, "assetType": code.group(1) if code else "",
                     "side": SIDES[m.group("type")], "amount": amt, "tradeDate": iso(m.group("td")),
                     "notified": iso(m.group("nd")), "owner": owner})
    expected = len(CODE_RE.findall("\n".join(kept)))
    return rows, expected

def pdf_to_text(pdf_bytes):
    p = subprocess.run(["pdftotext", "-layout", "-", "-"], input=pdf_bytes, capture_output=True, timeout=120)
    if p.returncode != 0: raise RuntimeError("pdftotext failed")
    return p.stdout.decode("utf-8", errors="replace")

def person_name(m):
    parts = [m.findtext("First") or "", m.findtext("Last") or "", m.findtext("Suffix") or ""]
    n = " ".join(x.strip() for x in parts if x.strip())
    return n.title() if n.isupper() else n

def house_filings(year, today, days):
    root = ET.fromstring(fetch(f"{HOUSE_BASE}/financial-pdfs/{year}FD.xml"))
    out = []
    for m in root:
        if m.findtext("FilingType") != "P": continue
        try: fd = dt.datetime.strptime(m.findtext("FilingDate"), "%m/%d/%Y").date()
        except (TypeError, ValueError): continue
        if (today - fd).days > days: continue
        out.append({"doc": (m.findtext("DocID") or "").strip(), "name": person_name(m), "state": (m.findtext("StateDst") or "").strip(),
                    "filed": fd.isoformat(), "year": year})
    return out

def build_house(prev_rows, prev_scanned, today, days, delay, log):
    filings = []
    for y in sorted({today.year, (today - dt.timedelta(days=days)).year}):
        try: filings += house_filings(y, today, days)
        except Exception as e: log(f"warn: House index {y}: {e}")
    if not filings: raise RuntimeError("House filing index unavailable")
    by_doc = {}
    for r in prev_rows: by_doc.setdefault(r["doc"], []).append(r)
    rows, stats = [], {"filings": len(filings), "reused": 0, "parsed": 0, "unreadable": 0, "mismatch": 0}
    unreadable, scanned = [], []
    for f in filings:
        if f["doc"] in by_doc:
            rows += by_doc[f["doc"]]; stats["reused"] += 1; continue
        if f["doc"] in prev_scanned:             # image-only (scanned/paper) filing seen before: nothing to read, do not download again
            stats["unreadable"] += 1; unreadable.append(f["doc"]); scanned.append(f["doc"]); continue
        url = f"{HOUSE_BASE}/ptr-pdfs/{f['year']}/{f['doc']}.pdf"
        try:
            time.sleep(delay)
            text = pdf_to_text(fetch(url))
            got, expected = parse_ptr_text(text)
        except Exception as e:
            log(f"warn: {f['doc']} {f['name']}: {e}"); stats["unreadable"] += 1; unreadable.append(f["doc"]); continue
        if not got:                              # scanned/handwritten filing or an unknown layout: nothing to show, link only
            stats["unreadable"] += 1; unreadable.append(f["doc"]); scanned.append(f["doc"]); log(f"skip (no table text): {f['doc']} {f['name']}"); continue
        if len(got) != expected:                 # parser disagrees with the number of assets listed: keep out rather than guess
            stats["mismatch"] += 1; unreadable.append(f["doc"]); log(f"skip (row count {len(got)} != {expected}): {f['doc']} {f['name']}"); continue
        stats["parsed"] += 1
        for g in got:
            rows.append({"p": f["name"], "c": "House", "st": f["state"], "t": g["ticker"], "a": g["asset"], "ty": g["assetType"],
                         "s": g["side"], "amt": g["amount"], "td": g["tradeDate"], "fd": f["filed"], "o": g["owner"],
                         "doc": f["doc"], "u": url, "src": "house-clerk"})
    stats["unreadableDocs"] = unreadable; stats["scannedDocs"] = scanned
    return rows, stats

# ----------------------------------------------------------------------------- Senate (community CC0 dataset)
def build_senate(today, days, log):
    """Senate rows from LuxAlgo/market-trackers-data (CC0, parsed from Senate eFD). Returns (rows, source-info)."""
    info = {"id": "senate", "name": "U.S. Senate eFD, via LuxAlgo community dataset (CC0)",
            "url": "https://github.com/LuxAlgo/market-trackers-data", "official": "https://efdsearch.senate.gov/search/home/"}
    try:
        data = []
        for fn in sorted({f"snapshot-{today.year}.json.gz", f"snapshot-{(today - dt.timedelta(days=days)).year}.json.gz"}):
            try: data += json.loads(gzip.decompress(fetch(f"{LUX_BASE}/congress/trades/{fn}")))
            except urllib.error.HTTPError as e:
                if e.code != 404: raise
        try: man = json.loads(fetch(f"{LUX_BASE}/manifest.json")); asof = man["datasets"]["congress-trades"]["lastIngestedAt"][:10]
        except Exception: asof = ""
    except Exception as e:
        log(f"warn: Senate community dataset unavailable: {e}")
        info.update({"status": "unavailable", "rows": 0}); return [], info
    rows = []
    for r in data:
        if r.get("chamber") != "senate" or (r.get("provenance") or {}).get("needsReview"): continue
        try: fd = dt.date.fromisoformat(r["filedAt"])
        except Exception: continue
        if (today - fd).days > days: continue
        m = r.get("member") or {}
        side = r.get("side") or ""
        rows.append({"p": re.sub(r"^(Hon\.|Sen\.)\s+", "", m.get("name", "")).strip(), "c": "Senate", "st": m.get("state", ""),
                     "t": r.get("ticker") or "", "a": re.sub(r"\s+", " ", r.get("assetDescription") or "").strip()[:140],
                     "ty": SENATE_TYPES.get(r.get("assetType"), "OT") if r.get("assetType") else "", "s": {"buy": "buy", "sell": "sell", "exchange": "exchange"}.get(side, side),
                     "amt": (r.get("amountRange") or {}).get("text", ""), "td": r.get("transactedAt") or "", "fd": r["filedAt"],
                     "o": r.get("owner") if r.get("owner") not in (None, "self") else "", "doc": r.get("docId", ""),
                     "u": (r.get("provenance") or {}).get("sourceUrl", ""), "src": "senate-efd-community"})
    info.update({"status": "ok" if rows else "empty", "rows": len(rows), "asOf": asof})
    return rows, info

# ----------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=120, help="keep filings from the last N days")
    ap.add_argument("--delay", type=float, default=0.6, help="seconds between PDF downloads")
    ap.add_argument("--no-senate", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=OUTPUTS[0])
    a = ap.parse_args(argv)
    log = lambda s: print(s, file=sys.stderr)
    today = dt.datetime.now(dt.timezone.utc).date()
    prev = {}
    try:
        with open(a.out, encoding="utf-8") as f: prev = json.load(f)
    except (OSError, ValueError): pass
    prev_house = [r for r in prev.get("trades", []) if r.get("c") == "House"]
    prev_scanned = set(next((s.get("scannedDocs", []) for s in prev.get("sources", []) if s.get("id") == "house"), []))
    house_rows, hs = build_house(prev_house, prev_scanned, today, a.days, a.delay, log)
    sen_rows, sinfo = ([], {"id": "senate", "status": "skipped", "rows": 0}) if a.no_senate else build_senate(today, a.days, log)
    if not a.no_senate and sinfo["status"] == "unavailable":      # keep last known Senate rows rather than dropping them
        sen_rows = [r for r in prev.get("trades", []) if r.get("c") == "Senate"]
        sinfo["rows"] = len(sen_rows); sinfo["status"] = "stale (kept previous)" if sen_rows else "unavailable"
        old = next((s for s in prev.get("sources", []) if s.get("id") == "senate"), {})
        sinfo["asOf"] = old.get("asOf", "")
    for r in house_rows + sen_rows:               # keep the file small: the apps rebuild House PDF links from doc + filing year
        r.pop("src", None)
        if r["c"] == "House": r.pop("u", None)
    trades = sorted(house_rows + sen_rows, key=lambda r: (r["fd"], r["td"]), reverse=True)[:MAX_ROWS]
    out = {"schema": 1, "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "windowDays": a.days,
           "note": NOTE, "assetTypes": {c: ASSET_TYPES.get(c, c) for c in sorted({r["ty"] for r in trades if r["ty"]})},
           "sources": [{"id": "house", "name": "U.S. House Clerk, Periodic Transaction Reports (official PDFs)",
                        "url": "https://disclosures-clerk.house.gov/FinancialDisclosure", "status": "ok" if house_rows else "empty",
                        "rows": len(house_rows), "filings": hs["filings"], "filingsParsed": hs["parsed"] + hs["reused"],
                        "filingsNotRead": hs["unreadable"] + hs["mismatch"], "unreadableDocs": hs["unreadableDocs"], "scannedDocs": hs["scannedDocs"]}, sinfo],
           "trades": trades}
    same = all(prev.get(k) == out.get(k) for k in ("trades", "sources", "assetTypes", "note", "windowDays"))
    if same and prev.get("generated"):             # nothing changed: keep the old stamp so the nightly job makes no commit
        out["generated"] = prev["generated"]
    log(f"House: {hs}; Senate: {sinfo.get('status')} rows={sinfo.get('rows')}; total rows={len(trades)}")
    if not a.dry_run:
        text = json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n"
        for p in {a.out, *OUTPUTS} if a.out == OUTPUTS[0] else [a.out]:
            os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f: f.write(text)
    return 0

if __name__ == "__main__":
    sys.exit(main())
