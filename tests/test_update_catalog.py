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
        self.assertGreaterEqual(self.c["version"], 1)
    def test_bundled_asset_matches(self):
        p = os.path.join(os.path.dirname(__file__), "..", "android/app/src/main/assets/catalog.json")
        self.assertEqual(json.load(open(p)), self.c)

if __name__ == "__main__":
    unittest.main()
