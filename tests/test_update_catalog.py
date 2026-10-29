import json, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import update_catalog as u

def tt(text, links=None): return {"type": "text", "text": text, **({"marks": [{"type": "link", "attrs": {"href": links}}]} if links else {})}
def block(kind, *inl, level=3):
    d = {"type": kind, "content": list(inl)}
    if kind == "heading": d["attrs"] = {"level": level}
    return d
def page(blocks, title="Test post", slug="test"):
    doc = {"post": {"web_title": title, "slug": slug, "override_scheduled_at": "2026-01-02T00:00:00Z"},
           "page": {"viewable_page_version": {"content": {"type": "doc", "content": blocks}}}}
    return "<html><script>window.__remixContext = " + json.dumps({"state": {"loaderData": {"routes/p/$slug": doc}}}) + ";</script></html>"

class Parse(unittest.TestCase):
    def test_numbered_heading_and_url_paragraph(self):
        h = page([block("heading", tt("296. EXRX"), level=2),
                  block("paragraph", tt("https://exrx.net/", "https://exrx.net/")),
                  block("paragraph", tt("Find exercises for any muscle.")),
                  block("paragraph", tt("TikTok: https://www.tiktok.com/@setupspawn/video/1", "https://www.tiktok.com/@setupspawn/video/1"))])
        meta, items = u.parse_post(h, "https://www.mattymctech.com/p/x")
        self.assertEqual(len(items), 1)
        self.assertEqual((items[0]["name"], items[0]["url"], items[0]["number"]), ("EXRX", "https://exrx.net/", 296))
        self.assertEqual(items[0]["description"], "Find exercises for any muscle.")
        self.assertTrue(items[0]["video"].startswith("https://www.tiktok.com/@setupspawn"))
        self.assertFalse(meta["gated"])

    def test_gated_content_after_break_is_never_read(self):
        h = page([block("heading", tt("A Tool (Part 1)", "https://a.example"), ), block("paragraph", tt("Does a thing.")),
                  {"type": "subscriberBreak"},
                  block("heading", tt("Hidden Tool (Part 2)", "https://hidden.example")), block("paragraph", tt("secret"))])
        meta, items = u.parse_post(h, "u")
        self.assertTrue(meta["gated"])
        self.assertEqual([i["name"] for i in items], ["A Tool"])
        self.assertNotIn("hidden.example", json.dumps(items))

    def test_sponsor_blocks_are_skipped(self):
        ad = "https://x.example/?utm_source=beehiiv&_bhiiv=opp_1"
        h = page([block("heading", tt("Try our thing now")), block("paragraph", tt("Buy", ad)),
                  block("heading", tt("Real Tool (Part 3)", "https://real.example")), block("paragraph", tt("Useful."))])
        _, items = u.parse_post(h, "u")
        self.assertEqual([i["url"] for i in items], ["https://real.example"])

    def test_multi_tool_heading(self):
        h = page([block("heading", tt("Photoshop → "), tt("GIMP", "https://gimp.org"), tt(" | "), tt("Photopea", "https://photopea.com")),
                  block("paragraph", tt("GIMP is open source. Photopea runs in your browser."))])
        _, items = u.parse_post(h, "u")
        self.assertEqual({i["name"] for i in items}, {"GIMP", "Photopea"})
        self.assertIn("browser", [i for i in items if i["name"] == "Photopea"][0]["description"])

class Helpers(unittest.TestCase):
    def test_url_key_and_clean(self):
        self.assertEqual(u.url_key("https://www.Synthesia.io/?utm_source=chatgpt.com"), "synthesia.io")
        self.assertEqual(u.url_key("http://synthesia.io/"), "synthesia.io")
        self.assertEqual(u.clean_url("https://x.com/a?utm_source=z&q=1"), "https://x.com/a?q=1")
    def test_clean_name(self):
        self.assertEqual(u.clean_name("🎬 223. Moviewiser"), "Moviewiser")
        self.assertEqual(u.clean_name("Amazon Style Snap (Part 22)"), "Amazon Style Snap")
        self.assertEqual(u.clean_name("277. Google GenType - gentype.withgoogle.com"), "Google GenType")
    def test_categorize_and_fallback(self):
        self.assertEqual(u.categorize("Foo", "AI image generator")[0], "ai")
        self.assertEqual(u.categorize("Bar", "find coupons and promo codes")[0], "shopping")
        self.assertEqual(u.categorize("Zed", "something indescribable")[0], "uncat")
    def test_override_wins(self):
        self.assertEqual(u.categorize("Foo", "AI thing", None, "", {"k": {"category": "fun", "tags": ["x"]}}, "k"), ("fun", ["x"]))

class Merge(unittest.TestCase):
    def item(self, name, url, cat="fun"):
        return {"id": u.make_id(url), "name": name, "url": url, "host": "h", "description": "", "category": cat, "tags": [], "sources": []}
    def test_new_items_get_new_version_and_old_are_kept(self):
        old = {"version": 3, "items": [self.item("A", "https://a.com")]}
        inc = [self.item("A", "https://a.com"), self.item("B", "https://b.com")]
        out, added = u.merge_catalog(old, inc, today="2026-11-01")
        self.assertEqual(out["version"], 4); self.assertEqual([i["name"] for i in added], ["B"])
        self.assertEqual(added[0]["addedVersion"], 4); self.assertEqual(out["itemCount"], 2)
    def test_no_change_keeps_version(self):
        old = {"version": 3, "items": [self.item("A", "https://a.com")]}
        out, added = u.merge_catalog(old, [self.item("A", "https://a.com")])
        self.assertEqual(out["version"], 3); self.assertEqual(added, [])
    def test_removed_items_are_not_deleted(self):
        old = {"version": 1, "items": [self.item("A", "https://a.com"), self.item("B", "https://b.com")]}
        out, _ = u.merge_catalog(old, [self.item("A", "https://a.com")])
        self.assertEqual(out["itemCount"], 2)
    def test_dedupe_across_posts(self):
        raw = [{"name": "S", "url": "https://synthesia.io", "description": "short", "post": {"title": "P1", "date": "d", "url": "u1"}},
               {"name": "S", "url": "https://www.synthesia.io/?utm_source=x", "description": "a longer description", "post": {"title": "P2", "date": "d", "url": "u2"}}]
        items = u.normalise(raw, {})
        self.assertEqual(len(items), 1); self.assertEqual(len(items[0]["sources"]), 2); self.assertEqual(items[0]["description"], "a longer description")

class Sheets(unittest.TestCase):
    def test_csv_columns_are_mapped_to_fields_and_tags(self):
        csv_text = "Tool,Link,What it does,Category,Use,Pricing\nFoo,https://foo.com,Does foo,Utilities,pdf; convert,Free\nBad,not a url,x,y,z,w\n"
        its = u.parse_sheet_csv(csv_text, "Test sheet", "https://docs.google.com/x")
        self.assertEqual(len(its), 1)
        items = u.normalise(its, {})
        self.assertEqual(items[0]["name"], "Foo"); self.assertIn("pdf", items[0]["tags"]); self.assertIn("free", items[0]["tags"])
        self.assertEqual(items[0]["extra"]["pricing"], "Free")
        self.assertEqual(items[0]["sources"][0]["title"], "Sheet: Test sheet")
    def test_google_sheet_url_becomes_csv_export(self):
        self.assertEqual(u.sheet_csv_url("https://docs.google.com/spreadsheets/d/ABC_1/edit#gid=5"),
                         "https://docs.google.com/spreadsheets/d/ABC_1/export?format=csv&gid=5")

PUB = "https://docs.google.com/spreadsheets/d/e/2PACX-abc/pubhtml"
HEADERLESS = (",,,\n,Want to Support? Buy me a coffee,,\n,https://www.buymeacoffee.com/x,,\n,,,\n"
              "1,Muscle Wiki,https://musclewiki.com/,Pick a muscle and find workouts\n"
              "2,Airport Wifi,https://bit.ly/abc,Find the WiFi Passwords at airports\n"
              "3,3 Websites for School,https://bit.ly/zzz,Link to TikTok Showing websites for School\n"
              "4,Old TikTok,https://www.tiktok.com/@x/video/1,demo\n"
              "Bonus 5,Coding Game,https://www.codingame.com/start,Learn how to code\n"
              ",,https://www.wolframalpha.com/,Solve homework\n"
              "6,This is it!,You're literally here already,List of all Websites\n"
              "7,Typo,https://www..ilovepdf.com ,All PDF tools\n")
HEADED = ",Website Name,Link,Description\n1,Geo Guessr,https://www.geoguessr.com/,Guess where you are\n2,OOPS Forgot this one,,\n"

class SheetImport(unittest.TestCase):
    def test_headerless_tab_is_mapped_by_position_and_junk_rows_skipped(self):
        rep = {}
        its = u.parse_sheet_csv(HEADERLESS, "Site list", PUB, {"name": "Powerful Websites"}, rep)
        self.assertEqual([i["name"] for i in its], ["Muscle Wiki", "Airport Wifi", "Coding Game", "Wolframalpha", "Typo"])
        self.assertEqual(its[0]["number"], 1); self.assertIsNone(its[2]["number"])  # "Bonus 5" is not a plain number
        self.assertEqual(its[0]["description"], "Pick a muscle and find workouts")
        whys = sorted(x["why"] for x in rep["skipped"])
        self.assertIn("link to a TikTok video, not a tool", whys)
        self.assertIn("not a web address", whys)
        self.assertEqual(sum(w.startswith("link to a TikTok") for w in whys), 2)
        self.assertFalse(any("buymeacoffee" in json.dumps(i) for i in its))

    def test_header_tab_with_website_name_column(self):
        rep = {}
        its = u.parse_sheet_csv(HEADED, "Site list", PUB, {"name": "Cure Boredom", "hint": "fun", "tag": "cure-boredom"}, rep)
        self.assertEqual(len(its), 1)
        self.assertEqual((its[0]["name"], its[0]["hint"]), ("Geo Guessr", "fun"))
        self.assertEqual(rep["skipped"][0]["why"], "no web address")
        items = u.normalise(its, {})
        self.assertIn("cure-boredom", items[0]["tags"])
        self.assertEqual(items[0]["sources"], [{"title": "Sheet: Cure Boredom", "date": "", "url": PUB, "number": 1}])

    def test_sheet_source_is_stable_so_monthly_runs_do_not_bump_version(self):
        its = u.parse_sheet_csv(HEADED, "S", PUB, {"name": "T"})
        a = u.normalise(its, {}); old, _ = u.merge_catalog({"version": 1, "items": []}, a, today="2026-01-01")
        again = u.normalise(u.parse_sheet_csv(HEADED, "S", PUB, {"name": "T"}), {})
        out, added = u.merge_catalog(old, again, today="2026-02-01")
        self.assertEqual((out["version"], added), (2, []))

    def test_sheet_row_merges_into_newsletter_item_and_records_both_sources(self):
        post = {"name": "Geo", "url": "https://geoguessr.com", "description": "", "post": {"title": "Post", "date": "2026-01-01", "url": "pu"}}
        its = u.parse_sheet_csv(HEADED, "S", PUB, {"name": "T"})
        items = u.normalise([post] + its, {})
        self.assertEqual(len(items), 1)
        self.assertEqual([s["title"] for s in items[0]["sources"]], ["Post", "Sheet: T"])
        self.assertEqual(items[0]["description"], "Guess where you are")

    def test_tabs_are_discovered_from_pubhtml_and_csv_urls_built(self):
        html_ = ('items.push({name: "Powerful Websites", pageUrl: "https:\\/\\/x\\/pubhtml\\/sheet?headers\\x3dfalse&gid=0", gid: "0", initialSheet: true});'
                 'items.push({name: "Cure Boredom", pageUrl: "https:\\/\\/x", gid: "343771459", initialSheet: false});')
        self.assertEqual(u.discover_tabs(html_), [("0", "Powerful Websites"), ("343771459", "Cure Boredom")])
        self.assertEqual(u.sheet_csv_url(PUB, "343771459"), "https://docs.google.com/spreadsheets/d/e/2PACX-abc/pub?gid=343771459&single=true&output=csv")

    def test_override_can_rename_and_fix_url_without_forcing_category(self):
        ov = {"wolframalpha.com": {"name": "Wolfram Alpha"}, "bit.ly/abc": {"url": "https://example.org/real", "name": "Real"}}
        its = u.parse_sheet_csv(HEADERLESS, "S", PUB, {"name": "T"})
        items = {i["name"]: i for i in u.normalise(its, ov)}
        self.assertIn("Wolfram Alpha", items); self.assertIn("Real", items)
        self.assertEqual(items["Real"]["url"], "https://example.org/real")
        self.assertEqual(items["Typo"]["url"], "https://www.ilovepdf.com")

    def test_new_live_category_exists(self):
        self.assertEqual(u.CAT_NAMES["live"], "Live Maps & Trackers")

    def test_developer_category_exists(self):
        self.assertEqual(u.CAT_NAMES["developer"], "Developer & Reverse Engineering")
        blurb = dict((c[0], c[2]) for c in u.CATEGORIES)["developer"]
        self.assertIn("Disassemblers", blurb)
        self.assertTrue(blurb.endswith("."))

class Credits(unittest.TestCase):
    def write(self, d, obj):
        p = os.path.join(d, "credits.json"); json.dump(obj, open(p, "w")); return p
    def test_load_validates(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            ok = u.load_credits(self.write(d, {"credits": [{"name": " A ", "contribution": "x", "url": "https://a.example/"}, {"name": "B", "contribution": "y"}]}))
            self.assertEqual(ok, [{"name": "A", "contribution": "x", "url": "https://a.example/"}, {"name": "B", "contribution": "y"}])
            for bad in ([{"name": "A"}], [{"contribution": "x"}], [{"name": "A", "contribution": "x", "url": "javascript:alert(1)"}], ["nope"]):
                with self.assertRaises(ValueError): u.load_credits(self.write(d, {"credits": bad}))
    def test_credits_only_bumps_version_once_and_syncs_copies(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            cat = os.path.join(d, "catalog.json"); asset = os.path.join(d, "a", "catalog.json"); docs = os.path.join(d, "docs", "catalog.json")
            json.dump({"version": 5, "date": "2026-01-01", "items": [], "posts": []}, open(cat, "w"))
            cr = self.write(d, {"credits": [{"name": "A", "contribution": "x"}]})
            args = ["--credits-only", "--catalog", cat, "--credits", cr, "--assets", asset, "--docs", docs]
            self.assertEqual(u.main(args), 0)
            c = json.load(open(cat)); self.assertEqual(c["version"], 6); self.assertEqual(c["credits"], [{"name": "A", "contribution": "x"}])
            self.assertEqual(json.load(open(asset)), c); self.assertEqual(json.load(open(docs)), c)
            self.assertEqual(u.main(args), 0)                       # unchanged -> no bump
            self.assertEqual(json.load(open(cat))["version"], 6)
            self.write(d, {"credits": [{"name": "A", "contribution": "x"}, {"name": "B", "contribution": "y", "url": "https://b.example"}]})
            u.main(args); self.assertEqual(json.load(open(cat))["version"], 7)
    def test_bad_credits_file_is_an_error(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            cat = os.path.join(d, "catalog.json"); json.dump({"version": 1, "items": [], "posts": []}, open(cat, "w"))
            self.assertEqual(u.main(["--credits-only", "--catalog", cat, "--assets", "", "--docs", "", "--credits", self.write(d, {"credits": [{"name": "x"}]})]), 2)

class Shipped(unittest.TestCase):
    def setUp(self):
        self.c = json.load(open(os.path.join(os.path.dirname(__file__), "..", "catalog.json")))
    def test_catalog_shape(self):
        ids = [i["id"] for i in self.c["items"]]
        self.assertEqual(len(ids), len(set(ids)))
        keys = [u.url_key(i["url"]) for i in self.c["items"]]
        self.assertEqual(len(keys), len(set(keys)), "duplicate URLs")
        cats = {x["id"] for x in self.c["categories"]}
        for i in self.c["items"]:
            self.assertTrue(i["url"].startswith("http"), i)
            self.assertIn(i["category"], cats)
            self.assertTrue(i["name"] and i["sources"])
        self.assertGreaterEqual(self.c["version"], 2)
    def test_sheet_import_is_in_the_shipped_catalog(self):
        sheet_items = [i for i in self.c["items"] if any(s["title"].startswith("Sheet:") for s in i["sources"])]
        self.assertGreater(len(sheet_items), 150)
        self.assertGreater(len(self.c["items"]), 200)
        self.assertEqual(sorted(t["name"] for t in self.c["sheets"][0]["tabs"]), ["Cure Boredom", "Powerful Websites"])
        blob = json.dumps(self.c["items"])
        self.assertNotIn("go2cloud", blob); self.assertNotIn("bit.ly", blob); self.assertNotIn("tiktok.com/@setupspawn/video/6951742734872988934", blob)
    def test_sources_json_lists_the_public_sheet(self):
        s = json.load(open(os.path.join(os.path.dirname(__file__), "..", "sources.json")))
        self.assertEqual(len(s["sheets"]), 1); self.assertIn("/pubhtml", s["sheets"][0]["url"])
    def test_shipped_credits(self):
        cr = u.load_credits(os.path.join(os.path.dirname(__file__), "..", "credits.json"))
        self.assertEqual(cr[0]["name"], "Matty McTech"); self.assertEqual(cr[0]["url"], "https://www.mattymctech.com/")
        self.assertEqual(self.c["credits"], cr)
        self.assertGreaterEqual(self.c["version"], 3)
    def test_docs_copy_matches(self):
        p = os.path.join(os.path.dirname(__file__), "..", "docs/catalog.json")
        self.assertEqual(json.load(open(p)), self.c)
    def test_bundled_asset_matches(self):
        p = os.path.join(os.path.dirname(__file__), "..", "android/app/src/main/assets/catalog.json")
        self.assertEqual(json.load(open(p)), self.c)

class CategoryIcons(unittest.TestCase):
    root = os.path.join(os.path.dirname(__file__), "..")
    def setUp(self):
        self.icons = json.load(open(os.path.join(self.root, "icons.json")))
        self.c = json.load(open(os.path.join(self.root, "catalog.json")))
    def test_every_category_has_a_distinct_known_icon(self):
        names = [u.icon_for(cid, self.icons) for cid, *_ in u.CATEGORIES]
        self.assertEqual(len(names), len(set(names)))
        for n in names:
            self.assertIn(n, self.icons["icons"]); self.assertTrue(all(d[:1] in "Mm" for d in self.icons["icons"][n]))
    def test_unknown_category_gets_default(self):
        self.assertEqual(u.icon_for("brand-new", self.icons), self.icons["default"])
        self.assertIn(self.icons["default"], self.icons["icons"])
    def test_catalog_categories_carry_matching_icon_field(self):
        self.assertEqual([c["icon"] for c in self.c["categories"]], [u.icon_for(c["id"], self.icons) for c in self.c["categories"]])
        self.assertEqual(len(self.c["categories"]), len(u.CATEGORIES))
    def test_copies_are_identical(self):
        src = open(os.path.join(self.root, "icons.json"), "rb").read()
        for dst in ("docs/icons.json", "android/app/src/main/assets/icons.json"):
            self.assertEqual(open(os.path.join(self.root, dst), "rb").read(), src, dst)
    def test_sync_icons_copies_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            dst = os.path.join(d, "x", "icons.json"); u.sync_icons([dst])
            self.assertEqual(json.load(open(dst)), self.icons)

class LinkFixes(unittest.TestCase):
    root = os.path.join(os.path.dirname(__file__), "..")
    def setUp(self):
        self.c = json.load(open(os.path.join(self.root, "catalog.json")))
        self.ov = json.load(open(os.path.join(self.root, "overrides.json")))
        self.items = {i["id"]: i for i in self.c["items"]}
    def test_capitol_trades_points_at_the_real_site(self):
        i = self.items["app-capitoltrades-com"]
        self.assertEqual((i["url"], i["host"], i["category"]), ("https://www.capitoltrades.com/", "capitoltrades.com", "money"))
        self.assertFalse([x for x in self.c["items"] if "www.app." in x["url"]])
    def test_amazon_warehouse_uses_resale_page(self):
        self.assertIn("Amazon-Resale", self.items["amazon-com-warehouse-deals"]["url"])
    def test_congress_trading_sources_added_under_money(self):
        for iid in ("quiverquant-com-congresstrading", "disclosures-clerk-house-gov-financialdisclosure",
                    "efdsearch-senate-gov-search-home", "unusualwhales-com-politics"):
            self.assertEqual(self.items[iid]["category"], "money", iid)
            self.assertTrue(self.items[iid]["url"].startswith("https://"))
            self.assertGreaterEqual(self.items[iid]["addedVersion"], 4)
    def test_developer_tools_match_the_hand_added_list(self):
        reddit = "https://www.reddit.com/r/SATNA_PROJECT/comments/1xg6lxl/the_ai_reverseengineering_toolkit_free_tools/"
        manual = json.load(open(os.path.join(self.root, "manual_items.json")))
        expected = [m for m in manual if m.get("post_url") == reddit]
        self.assertEqual(len(expected), 90)
        by_url = {i["url"]: i for i in self.c["items"]}
        for m in expected:
            i = by_url[m["url"]]
            self.assertEqual((i["name"], i["description"], i["category"]), (m["name"], m["description"], "developer"))
            self.assertTrue(any(s.get("url") == reddit for s in i["sources"]), m["name"])
        for name in ("REA", "RevAPK", "de4dot"):
            self.assertIn(name, {i["name"] for i in self.c["items"] if i["category"] == "developer"})
        cat = next(c for c in self.c["categories"] if c["id"] == "developer")
        self.assertEqual((cat["name"], cat["icon"]), ("Developer & Reverse Engineering", "code"))

    def test_sheet_row_with_bad_address_is_redirected_and_keeps_its_id(self):
        raw = [{"name": "Capitol Trades", "url": "https://www.app.capitoltrades.com", "description": "d", "hint": None, "replaces": None,
                "video": None, "number": None, "post": {"title": "Sheet", "date": "", "url": "x"}}]
        out = u.normalise(raw, self.ov)
        self.assertEqual([(o["id"], o["url"]) for o in out], [("app-capitoltrades-com", "https://www.capitoltrades.com/")])
        merged, added = u.merge_catalog(self.c, out)
        self.assertEqual(added, [])                                  # no duplicate on the next monthly crawl

if __name__ == "__main__":
    unittest.main()
