#!/usr/bin/env python3
"""
update_catalog.py - re-crawl mattymctech.com and refresh catalog.json.

UNOFFICIAL fan-made directory. Standard library only (Python 3.9+).

What it does
  1. Reads https://www.mattymctech.com/sitemap.xml (+ /archive pages) to find every post.
  2. Downloads each post politely (default 1.2 s between requests) and extracts the tools/sites
     that are *openly readable*. Posts carry a "subscriber break" (the site says "Subscribe to
     keep reading"); everything after that break is NOT read or stored. This script never signs
     up, logs in, or reads the hidden part of the page payload.
  3. Optionally imports public spreadsheets/CSV exports listed in sources.json ("sheets").
     Private / sign-in / email-gated sheets must NOT be listed.
  4. Categorises new items with simple keyword rules (see CATEGORY_RULES). Anything that does not
     match falls back to "Uncategorized / New". Hand-fixed categories live in overrides.json and
     are never overwritten. Rule-based categorisation is only a rough guess.
  5. Merges into the existing catalog.json: existing items are kept (ids are stable), new items
     get addedVersion = new catalog version, and version is bumped only if something changed.

Usage
  python3 update_catalog.py                      # crawl live site, rewrite catalog.json
  python3 update_catalog.py --cache .cache       # keep downloaded HTML in .cache (re-run offline with --offline)
  python3 update_catalog.py --dry-run            # show what would change, write nothing
"""
import argparse, csv, datetime as dt, html, io, json, os, re, sys, time
import urllib.request, urllib.error
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

BASE = "https://www.mattymctech.com"
UA = "Mozilla/5.0 (compatible; MattyToolsDirectoryBot/1.0; unofficial fan-made directory)"
HERE = os.path.dirname(os.path.abspath(__file__))
UNCAT = "Uncategorized / New"

# ----------------------------------------------------------------------------- categories
CATEGORIES = [
    ("ai", "AI Tools", "Generate, summarise and create with AI"),
    ("tv", "Free TV & Movies", "Streaming, TV and what to watch"),
    ("fun", "Fun & Games", "Games, pranks, curiosities and time-wasters"),
    ("music", "Music & Audio", "Listen, make and remix sound"),
    ("design", "Design & Creative", "Photo, video, art and design tools"),
    ("productivity", "Productivity & Utilities", "PDFs, files, calculators and everyday helpers"),
    ("learning", "Learning & Reference", "Courses, books, science and how-things-work"),
    ("security", "Security & Privacy", "Stay safe, private and informed online"),
    ("shopping", "Shopping & Deals", "Coupons, price checks and cheaper alternatives"),
    ("money", "Money, Jobs & Business", "Side hustles, remote jobs, finance and business"),
    ("lifestyle", "Health, Food & Home", "Fitness, recipes, home, garden and health"),
    ("travel", "Travel, Maps & Local", "Maps, travel, cars and local info"),
    ("uncat", UNCAT, "New items waiting for a category"),
]
CAT_NAMES = {c[0]: c[1] for c in CATEGORIES}

# keyword rules: (category id, tag, regex). Scored by number of matches in name+description+Category hint.
CATEGORY_RULES = [
    ("ai", r"(?-i:\bAI\b)|artificial intelligence|machine learning|\bGPT\b|text[- ]to[- ](speech|image|video)|generat(e|es|ive|or)\b.*\b(image|art|voice|video|music)|face swap|deepfake"),
    ("tv", r"\b(movie|movies|film|films|tv|television|stream(ing)?|netflix|hulu|iptv|episode|show|shows|cinema|anime|documentar)"),
    ("music", r"\b(music|song|songs|audio|playlist|radio|vocal|karaoke|podcast|dj|sequencer|synth|sound|artist|artists)\b"),
    ("design", r"\b(design|photo|photos|image editor|photoshop|illustrat|vector|video editor|animation|animate|3d|logo|font|fonts|palette|color|colour|draw|drawing|paint|background removal|remove\.bg|inpaint|collage|render)"),
    ("security", r"\b(privacy|private|secure|security|password|password manager|tracker|trackers|encrypt|vpn|scam|phishing|breach|hack|hacker|fake news|forensic|temp(orary)? mail|disposable|terms of service|spam)\b"),
    ("shopping", r"\b(coupon|coupons|promo|deal|deals|discount|cheaper|price|prices|outlet|sale|flyer|flyers|shopping|dupe|markup|review|reviews|buy)\b"),
    ("money", r"\b(job|jobs|remote work|freelanc\w*|side hustle|hustle|invest|investing|stock|stocks|tax|taxes|finance|financial|business|resume|career|salary|earn money|income|market)\b"),
    ("learning", r"\b(learn|learning|course|courses|education|educational|study|student|students|school|university|math|science|history|book|books|read|reading|encyclop|wiki|tutorial|language|translate|explore any subject|space|satellite|stars|planetarium|astronomy)\b"),
    ("lifestyle", r"\b(recipe|recipes|cook|cooking|food|meal|cocktail|drink|fitness|workout|exercise|muscle|health|sleep|garden|gardening|furniture|room|home|diet|calorie|grocer|kitchen)\b"),
    ("travel", r"\b(map|maps|travel|trip|flight|flying|airport|wifi|wi-fi|gas|road|driv(e|ing)|car|cars|auto parts|city|cities|street view|local|weather|hotel|navigation)\b"),
    ("fun", r"\b(game|games|gaming|play|prank|fun|weird|addictive|bored|boredom|puzzle|trivia|quiz|minecraft|retro|nostalgia|nostalgic|guess|rpg|dnd|dungeon)\b"),
    ("productivity", r"\b(pdf|convert|converter|calculator|calculate|spreadsheet|excel|document|documents|files?|ocr|summar|notes?|office|editor|download(er)?|tool|tools|productivity|free alternative|alternatives?|open-source|open source|compress|merge)\b"),
]
# first-match-wins priority for ties
PRIORITY = ["ai", "tv", "security", "shopping", "money", "music", "design", "learning", "lifestyle", "travel", "fun", "productivity"]
POST_CATEGORY_HINT = {  # the post's own "Category: X" line -> catalog category
    "technology": "productivity", "business": "money", "education": "learning", "gaming": "fun", "fun": "fun",
    "jobs": "money", "health": "lifestyle", "food": "lifestyle", "music": "music", "entertainment": "tv",
    "travel": "travel", "shopping": "shopping", "finance": "money", "security": "security",
}
USE_TAGS = [  # (tag, regex) - descriptive "use" tags
    ("free", r"\bfree\b|no cost|no charge|100% free"),
    ("no-signup", r"no (account|login|signup|sign-up|accounts|logins)|without (an )?account|no downloads?|no installs?"),
    ("in-browser", r"\bbrowser\b|\bonline\b|web[- ]based"),
    ("open-source", r"open[- ]source"),
    ("ai", r"(?-i:\bAI\b)|artificial intelligence"),
    ("video", r"\bvideo|videos|youtube|tiktok\b"),
    ("photo", r"\bphoto|photos|image|images|picture"),
    ("pdf", r"\bpdf"),
    ("map", r"\bmap|maps\b"),
    ("recipes", r"\brecipe|recipes|cooking|meal"),
    ("games", r"\bgame|games|gaming"),
    ("music", r"\bmusic|song|songs|playlist|radio"),
    ("jobs", r"\bjob|jobs|remote work|freelanc\w*"),
    ("alternative", r"alternative|replaces?\b"),
    ("weird-fun", r"\bprank|weird|addictive|bored"),
    ("privacy", r"\bprivacy|private|tracker|encrypt"),
    ("learning", r"\blearn|course|study|education"),
    ("deals", r"\bcoupon|\bdeals?\b|\bdiscount|\bcheaper|\bprices?\b"),
]

# ----------------------------------------------------------------------------- http
def fetch(url, delay=0.0, retries=2, timeout=30):
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xml,text/csv,*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read().decode("utf-8", errors="replace")
            if delay: time.sleep(delay)
            return data
        except Exception as e:  # noqa
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"fetch failed {url}: {last}")

def cached_fetch(url, cache, offline, delay):
    if cache:
        os.makedirs(cache, exist_ok=True)
        fn = os.path.join(cache, re.sub(r"[^A-Za-z0-9._-]+", "_", url.replace(BASE, "")) or "index")
        if os.path.exists(fn) and (offline or os.path.getsize(fn) > 0 and cache_fresh(fn)):
            return open(fn, encoding="utf-8").read()
        if offline: raise RuntimeError("offline and not cached: " + url)
        data = fetch(url, delay)
        open(fn, "w", encoding="utf-8").write(data)
        return data
    return fetch(url, delay)

def cache_fresh(fn, hours=6):
    return (time.time() - os.path.getmtime(fn)) < hours * 3600

# ----------------------------------------------------------------------------- post discovery
def list_post_urls(cache=None, offline=False, delay=1.2):
    urls = []
    try:
        sm = cached_fetch(BASE + "/sitemap.xml", cache, offline, delay)
        urls += [u for u in re.findall(r"<loc>([^<]+)</loc>", sm) if "/p/" in u]
    except Exception as e:
        print("warn: sitemap failed:", e, file=sys.stderr)
    # archive pagination as a cross-check (and fallback)
    for page in range(0, 12):
        try:
            h = cached_fetch(BASE + "/archive" + (f"?page={page}" if page else ""), cache, offline, delay)
        except Exception as e:
            print("warn: archive page", page, "failed:", e, file=sys.stderr); break
        found = re.findall(r'href="(/p/[^"#?]+)"', h)
        if page and not found: break
        urls += [BASE + f for f in found]
    seen, out = set(), []
    for u in urls:
        u = u.rstrip("/")
        if u not in seen: seen.add(u); out.append(u)
    return out

# ----------------------------------------------------------------------------- post parsing
SKIP_KEYS = {"contentGatePopup", "emailCapturePopup", "structureTiptapState", "structureTiptapStateDraft"}
BAD_LINK = re.compile(
    r"tiktok\.com|beehiiv\.com|mattymctech\.com|^mailto:|^tel:|_bhiiv=|bhcl_id=|subscriber_id|utm_source=(beehiiv|email|external)|"
    r"utm_medium=(paid|email|newsletter|dis_ad|referrals|cpc|email-media)|aff_id=|youtube\.com/@setupspawn|instagram\.com/setupspawn|"
    r"facebook\.com/SetupSpawn|x\.com/setupspawn|linkedin\.com/in/matty", re.I)

def load_remix(html_text):
    m = re.search(r"window\.__remixContext = ", html_text)
    if not m: raise ValueError("no remix context (site layout changed?)")
    obj, _ = json.JSONDecoder().raw_decode(html_text[m.end():])
    return obj["state"]["loaderData"]["routes/p/$slug"]

def _inline(n, links):
    if isinstance(n, list): return "".join(_inline(x, links) for x in n)
    if not isinstance(n, dict): return ""
    t = n.get("type")
    if t == "text":
        for mk in n.get("marks") or []:
            if mk.get("type") == "link": links.append((mk["attrs"]["href"], n["text"]))
        return n["text"]
    if t == "hardBreak": return "\n"
    return _inline(n["content"], links) if "content" in n else ""

def _blocks(o, out):
    if isinstance(o, list):
        for x in o: _blocks(x, out)
    elif isinstance(o, dict):
        t = o.get("type")
        if t == "subscriberBreak": out.append(("BREAK", "", [])); return
        if t in ("heading", "paragraph", "listItem") and "content" in o:
            links = []; txt = _inline(o["content"], links)
            out.append((t + (str((o.get("attrs") or {}).get("level", "")) if t == "heading" else ""), txt, links)); return
        for k, v in o.items():
            if k in SKIP_KEYS: continue
            if isinstance(v, (dict, list)): _blocks(v, out)

def open_blocks(html_text):
    """Return (post meta, blocks before the first subscriber break). Hidden content is never returned."""
    d = load_remix(html_text)
    blocks = []
    _blocks(d["page"]["viewable_page_version"]["content"], blocks)
    gated = False
    visible = []
    for b in blocks:
        if b[0] == "BREAK": gated = True; break
        visible.append(b)
    p = d["post"]
    meta = {
        "slug": p.get("slug") or d.get("slugInParams"),
        "title": (p.get("web_title") or "").strip(),
        "subtitle": p.get("web_subtitle") or "",
        "date": (p.get("override_scheduled_at") or p.get("created_at") or "")[:10],
        "gated": gated,
    }
    return meta, visible

NUM_RE = re.compile(r"^\W*(\d{1,3})\s*[.)]\s*(?=\S)")
PART_RE = re.compile(r"\(\s*(?:part|parts)?\s*(\d{1,3})\s*\)", re.I)

def good_links(links):
    return [(h, t) for h, t in links if h and not BAD_LINK.search(h) and re.match(r"^(https?://|www\.)", h)]

def clean_url(u):
    u = u.strip()
    if not re.match(r"^https?://", u): u = "https://" + u
    p = urlparse(u)
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    host = p.netloc.lower()
    path = p.path
    return urlunparse((p.scheme.lower(), host, path, "", urlencode(q), ""))

def url_key(u):
    p = urlparse(clean_url(u))
    return (re.sub(r"^www\.", "", p.netloc) + p.path.rstrip("/")).lower() + (("?" + p.query) if p.query else "")

def clean_name(text):
    t = text.replace("\n", " ").strip()
    t = NUM_RE.sub("", t)
    t = PART_RE.sub("", t)
    t = re.sub(r"\s+[-–—]\s+\S+\.[a-z]{2,}\S*\s*$", "", t)  # " - domain.com"
    t = re.sub(r"^[^\w(]+", "", t)  # leading emoji/punct
    t = re.sub(r"[\s:–—-]+$", "", t)
    return re.sub(r"\s+", " ", t).strip()

def number_of(text):
    m = NUM_RE.match(text.replace("\n", " "))
    if m: return int(m.group(1))
    m = PART_RE.search(text)
    return int(m.group(1)) if m else None

def is_starter(kind, text, links, nxt=None):
    first = text.strip().split("\n")[0]
    if kind in ("heading2", "heading3", "paragraph") and NUM_RE.match(first.replace("\n", " ")):
        return kind != "paragraph" or len(first) < 140
    if kind in ("heading2", "heading3") and PART_RE.search(first): return True
    if kind in ("heading2", "heading3") and good_links(links) and len(first.split()) <= 7: return True
    if kind in ("heading2", "heading3") and nxt and re.search(r"Platforms?:", nxt[1]): return True
    if kind == "paragraph" and re.search(r"\n\s*Category:", text) and re.search(r"\n\s*Link:\s*\S", text): return True
    return False

CLOSER = re.compile(r"^(that.s it|forward this|hit reply|reply to this|which one|enjoy discovering|want to sponsor|follow me|[-–—]\s*matty|see you|catch you|pro tip|thanks for|let me know)", re.I)
URL_ONLY = re.compile(r"^\s*(?:TikTok\s*[:/]?\s*)?(https?://\S+|www\.\S+)\s*$", re.I)
EMOJI_PREFIX = re.compile(r"^[^\w\"'“(]+")

def build_item(starter, group):
    kind, text, links = starter
    name = clean_name(text.split("\n")[0]) if kind == "paragraph" else clean_name(text)
    allblocks = [starter] + group
    all_links = good_links([l for b in allblocks for l in b[2]])
    # tool URL: first good link in heading, else first good link anywhere in the group
    head_links = good_links(links)
    url = None
    if head_links: url = head_links[0][0]
    else:
        for b in group:
            gl = good_links(b[2])
            if gl: url = gl[0][0]; break
    video = next((h for b in allblocks for h, _ in b[2] if "tiktok.com/@setupspawn" in h), None)
    # description lines
    desc_lines, cat_hint, use_for, replaces = [], None, None, None
    body_texts = [b[1] for b in group if b[0] in ("paragraph", "listItem")]
    if kind == "paragraph": body_texts = ["\n".join(text.split("\n")[1:])] + body_texts
    for bt in body_texts:
        for line in bt.split("\n"):
            s = EMOJI_PREFIX.sub("", line.strip()) if line.strip().startswith(("🎧", "🛠", "💰")) else line.strip()
            if not s: continue
            low = s.lower()
            if URL_ONLY.match(s) or low.startswith(("tiktok", "watch on tiktok", "watch tiktok", "link:")): continue
            if re.fullmatch(r"(watch (the )?tiktok.*|tiktok demo)", low): continue
            m = re.match(r"category:\s*(.+)", s, re.I)
            if m: cat_hint = m.group(1).strip(); continue
            m = re.match(r"use it for:\s*(.+)", s, re.I)
            if m: use_for = m.group(1).strip(); continue
            m = re.match(r"replaces:\s*(.+)", s, re.I)
            if m: replaces = m.group(1).strip(); continue
            s = re.sub(r"^what it does:\s*", "", s, flags=re.I)
            s = re.sub(r"\s*[/·]?\s*(watch (on )?tiktok.*|tiktok demo)\s*$", "", s, flags=re.I).strip()
            if s: desc_lines.append(s)
    desc = " ".join(desc_lines).strip()
    desc = re.split(r"\s*(?:That.s \d+ websites|We.re just getting started|Reply and tell|Forward this|Hit reply)", desc, flags=re.I)[0].strip()
    # single-paragraph "Name\nDesc\nCategory: ..\nUse it for: ..\nLink: ..": handled above
    if use_for and desc: desc = f"{desc} Use it for: {use_for}"
    if len(desc) > 320: desc = desc[:317].rsplit(" ", 1)[0] + "..."
    return {"name": name, "url": url, "description": desc, "hint": cat_hint, "replaces": replaces,
            "video": video, "number": number_of(text.split("\n")[0])}

def multi_items(starter, group):
    """Headings such as 'Photoshop -> GIMP | Photopea' or side-hustle blocks list several tools in one entry."""
    kind, text, links = starter
    gl = good_links(links)
    para_links = good_links([l for b in group for l in b[2]])
    cands = gl if len(gl) >= 2 else (para_links if re.search(r"Platforms?:", " ".join(b[1] for b in group)) else [])
    if len(cands) < 2 and not (len(cands) == 1 and re.search(r"Platforms?:", " ".join(b[1] for b in group))): return None
    desc = ""
    for b in group:
        if b[0] == "paragraph":
            first = b[1].split("\n")[0].strip()
            desc = re.sub(r"^[^\w\"“(]+", "", first)
            break
    out, seen = [], set()
    ctx = clean_name(text)
    for h, t in cands:
        if url_key(h) in seen: continue
        seen.add(url_key(h))
        nm = clean_name(t) if t and not t.startswith("http") and "|" not in t and "→" not in t else None
        if not nm: nm = domain_name(h)
        out.append({"name": nm, "url": h, "description": tool_desc(nm, ctx, desc), "hint": None,
                    "replaces": None, "video": None, "number": None})
    return out

def tool_desc(name, ctx, desc):
    """Pick the sentence about this tool; add 'Free alternative to X' for 'X -> Tool' headings."""
    sents = re.split(r"(?<=[.!?])\s+", desc) if desc else []
    mine = [x for x in sents if name.lower() in x.lower()]
    text = " ".join(mine) if mine else desc
    if "→" in ctx:
        left = ctx.split("→")[0].strip()
        text = f"Alternative to {left}. {text}".strip()
    elif not mine and ctx:
        text = f"{ctx}. {text}".strip()
    return text

def domain_name(u):
    host = re.sub(r"^www\.", "", urlparse(clean_url(u)).netloc)
    return host.split(".")[0].replace("-", " ").title()

def parse_post(html_text, post_url):
    meta, blocks = open_blocks(html_text)
    items, cur, group = [], None, []
    def flush():
        nonlocal cur, group
        if cur is None: return
        multi = multi_items(cur, group) if (not NUM_RE.match(cur[1].replace("\n", " ")) and not PART_RE.search(cur[1])) else None
        for it in (multi or [build_item(cur, group)]):
            if it["url"] and it["name"]: items.append(it)
        cur, group = None, []
    for bi, b in enumerate(blocks):
        kind, text, links = b
        if kind == "heading1": continue
        if text.strip() == "Keep Reading": break
        if kind == "paragraph" and CLOSER.match(text.strip()):
            flush(); continue
        if is_starter(kind, text, links, blocks[bi + 1] if bi + 1 < len(blocks) else None):
            flush(); cur = b
        elif kind.startswith("heading"):
            flush()  # an unrelated heading (sponsor, intro) closes the current entry
        elif cur is not None:
            group.append(b)
    flush()
    for it in items:
        it["post"] = {"title": meta["title"], "date": meta["date"], "url": post_url}
    return meta, items

# ----------------------------------------------------------------------------- categorisation
def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

def make_id(url):
    return slugify(url_key(url))[:80]

def categorize(name, desc, hint=None, host="", overrides=None, key=""):
    if overrides and key in overrides:
        o = overrides[key]
        return o["category"], list(o.get("tags", []))
    text = f"{name} {desc} {host}"
    scores = {}
    for cid, rx in CATEGORY_RULES:
        n = len(re.findall(rx, text, re.I))
        if n: scores[cid] = n
    if hint and POST_CATEGORY_HINT.get(hint.strip().split("/")[0].strip().lower()):
        scores.setdefault(POST_CATEGORY_HINT[hint.strip().split("/")[0].strip().lower()], 0)
        scores[POST_CATEGORY_HINT[hint.strip().split("/")[0].strip().lower()]] += 0.5
    cat = "uncat"
    if scores:
        best = max(scores.values())
        cat = next(c for c in PRIORITY if scores.get(c) == best)
    tags = [t for t, rx in USE_TAGS if re.search(rx, text, re.I)]
    return cat, tags

# ----------------------------------------------------------------------------- spreadsheets
SHEET_COLS = {
    "name": ("name", "tool", "site", "website", "title", "app"),
    "url": ("url", "link", "website url", "site url", "web"),
    "description": ("description", "desc", "what it does", "about", "notes", "summary"),
    "category": ("category", "type", "section"),
    "use": ("use", "uses", "use case", "use it for", "tags", "tag"),
    "pricing": ("pricing", "price", "cost", "free?"),
    "notes": ("notes", "note", "comment", "comments"),
}

def sheet_csv_url(u):
    """Turn a normal Google Sheets share URL into a CSV export URL (only works for sheets shared 'anyone with the link')."""
    m = re.match(r"https://docs\.google\.com/spreadsheets/d/([\w-]+)", u)
    if m and "export?format=csv" not in u and "output=csv" not in u:
        gid = re.search(r"[#&?]gid=(\d+)", u)
        return f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv" + (f"&gid={gid.group(1)}" if gid else "")
    return u

def parse_sheet_csv(text, source_name, source_url):
    rows = list(csv.reader(io.StringIO(text)))
    if not rows: return []
    head = [h.strip().lower() for h in rows[0]]
    def col(field):
        for a in SHEET_COLS[field]:
            if a in head: return head.index(a)
        return None
    idx = {f: col(f) for f in SHEET_COLS}
    if idx["url"] is None:  # maybe the name column holds URLs
        return []
    out = []
    for r in rows[1:]:
        g = lambda f: (r[idx[f]].strip() if idx[f] is not None and idx[f] < len(r) else "")
        url = g("url")
        if not url or " " in url or "." not in url: continue
        name = g("name") or domain_name(url)
        it = {"name": name, "url": url, "description": g("description"), "hint": g("category") or None,
              "replaces": None, "video": None, "number": None,
              "post": {"title": f"Sheet: {source_name}", "date": dt.date.today().isoformat(), "url": source_url},
              "extra": {k: g(k) for k in ("use", "pricing", "notes") if g(k)}}
        out.append(it)
    return out

# ----------------------------------------------------------------------------- merge
def merge_catalog(old, incoming, today=None):
    """Merge incoming items (already normalised, with id) into the old catalog dict. Returns (new catalog, list of new items)."""
    today = today or dt.date.today().isoformat()
    old_items = {i["id"]: i for i in old.get("items", [])}
    cur_version = int(old.get("version", 0))
    new_version = cur_version + 1
    added, changed = [], False
    for it in incoming:
        ex = old_items.get(it["id"])
        if ex is None:
            it = dict(it); it["addedVersion"] = new_version; it["added"] = today
            old_items[it["id"]] = it; added.append(it); changed = True
        else:
            # refresh text fields from the crawl, never touch category/tags chosen earlier unless still uncategorised
            for f in ("name", "url", "description", "video"):
                if it.get(f) and it[f] != ex.get(f): ex[f] = it[f]; changed = True
            srcs = ex.setdefault("sources", [])
            for s in it.get("sources", []):
                if s not in srcs: srcs.append(s); changed = True
            if ex.get("category") == "uncat" and it.get("category") != "uncat":
                ex["category"] = it["category"]; ex["tags"] = it.get("tags", []); changed = True
    out = dict(old)
    out["items"] = sorted(old_items.values(), key=lambda i: (i["category"], i["name"].lower()))
    if changed:
        out["version"] = new_version
        out["date"] = today
    else:
        out["version"] = cur_version
    out["itemCount"] = len(out["items"])
    return out, added

def normalise(raw_items, overrides):
    """raw extractor items -> catalog items (dedup by url key within the batch)."""
    by = {}
    for r in raw_items:
        url = clean_url(r["url"])
        key = orig_key = url_key(url)
        if (overrides.get(key) or {}).get("skip"): continue
        if (overrides.get(key) or {}).get("url"):  # corrected address for a moved site
            url = clean_url(overrides[key]["url"]); key = url_key(url)
        host = re.sub(r"^www\.", "", urlparse(url).netloc)
        src = {"title": r["post"]["title"], "date": r["post"]["date"], "url": r["post"]["url"]}
        if r.get("number"): src["number"] = r["number"]
        if key in by:
            ex = by[key]
            if src not in ex["sources"]: ex["sources"].append(src)
            if len(r.get("description", "")) > len(ex["description"]): ex["description"] = r["description"]
            continue
        cat, tags = categorize(r["name"], r.get("description", ""), r.get("hint"), host, overrides, orig_key)
        extra = r.get("extra") or {}
        if r.get("replaces"): tags.append("alternative")
        for k in ("use", "pricing"):
            if extra.get(k):
                tags += [slugify(x) for x in re.split(r"[;,/|]", extra[k]) if x.strip()][:4]
        item = {
            "id": make_id(url), "name": r["name"], "url": url, "host": host,
            "description": r.get("description", ""), "category": cat,
            "tags": sorted(set(tags)), "sources": [src],
        }
        if r.get("video"): item["video"] = r["video"]
        if r.get("replaces"): item["replaces"] = r["replaces"]
        if extra: item["extra"] = extra
        by[key] = item
    return list(by.values())

def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError:
        return default

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--catalog", default=os.path.join(HERE, "catalog.json"))
    ap.add_argument("--sources", default=os.path.join(HERE, "sources.json"))
    ap.add_argument("--manual", default=os.path.join(HERE, "manual_items.json"))
    ap.add_argument("--overrides", default=os.path.join(HERE, "overrides.json"))
    ap.add_argument("--cache", default=None, help="directory to cache downloaded pages")
    ap.add_argument("--offline", action="store_true", help="only use --cache, no network")
    ap.add_argument("--delay", type=float, default=1.2, help="seconds between requests")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--assets", default=os.path.join(HERE, "android/app/src/main/assets/catalog.json"),
                    help="also copy the catalog here (bundled in the app); '' to skip")
    a = ap.parse_args(argv)

    old = load_json(a.catalog, {"version": 0, "items": [], "posts": []})
    overrides = load_json(a.overrides, {})
    sources = load_json(a.sources, {"sheets": []})

    post_urls = list_post_urls(a.cache, a.offline, a.delay)
    print(f"found {len(post_urls)} posts", file=sys.stderr)
    raw, posts = [], []
    for u in post_urls:
        try:
            h = cached_fetch(u, a.cache, a.offline, a.delay)
            meta, items = parse_post(h, u)
        except Exception as e:
            print(f"warn: {u}: {e}", file=sys.stderr); continue
        posts.append({"slug": meta["slug"], "title": meta["title"], "date": meta["date"], "url": u,
                      "gated": meta["gated"], "toolsFound": len(items)})
        raw += items
        print(f"  {meta['date']} {meta['title'][:50]:50} gated={meta['gated']!s:5} tools={len(items)}", file=sys.stderr)
    # hand-curated items taken from openly readable post text (e.g. a how-to that names one tool)
    for m in load_json(a.manual, []):
        raw.append({"name": m["name"], "url": m["url"], "description": m.get("description", ""), "hint": None,
                    "replaces": None, "video": None, "number": None,
                    "post": {"title": m["post_title"], "date": m["post_date"], "url": m["post_url"]}})
    # public spreadsheets (optional)
    sheet_report = []
    for s in sources.get("sheets", []):
        try:
            csv_url = sheet_csv_url(s["url"])
            text = cached_fetch(csv_url, a.cache, a.offline, a.delay)
            if text.lstrip().lower().startswith(("<!doctype", "<html")):
                raise RuntimeError("not a public CSV (sign-in or access page returned) - skipped, nothing bypassed")
            its = parse_sheet_csv(text, s.get("name", "sheet"), s["url"])
            raw += its; sheet_report.append({"name": s.get("name"), "url": s["url"], "items": len(its)})
            print(f"  sheet {s.get('name')}: {len(its)} items", file=sys.stderr)
        except Exception as e:
            sheet_report.append({"name": s.get("name"), "url": s.get("url"), "error": str(e)})
            print(f"warn: sheet {s.get('name')}: {e}", file=sys.stderr)

    incoming = normalise(raw, overrides)
    new_cat, added = merge_catalog(old, incoming)
    new_cat.update({
        "schema": 1,
        "title": "Matty McTech tools directory (unofficial)",
        "source": BASE, "posts": sorted(posts, key=lambda p: p["date"], reverse=True),
        "sheets": sheet_report or old.get("sheets", []),
        "categories": [{"id": c[0], "name": c[1], "blurb": c[2]} for c in CATEGORIES],
        "note": "Unofficial fan-made directory. Only publicly readable (ungated) parts of posts are listed; "
                "categories for new items are keyword-guessed.",
    })
    print(f"posts={len(posts)} items={len(new_cat['items'])} new={len(added)} version={new_cat['version']}", file=sys.stderr)
    if not a.dry_run:
        for path in filter(None, [a.catalog, a.assets]):
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(new_cat, f, ensure_ascii=False, indent=1); f.write("\n")
    for it in added[:50]: print("NEW:", it["name"], it["url"], "->", CAT_NAMES[it["category"]])
    return 0

if __name__ == "__main__":
    sys.exit(main())
