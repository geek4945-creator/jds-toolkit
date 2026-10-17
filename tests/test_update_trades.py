import json, os, sys, unittest, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import update_trades as u
FX = os.path.join(os.path.dirname(__file__), "fixtures")
ROOT = os.path.join(os.path.dirname(__file__), "..")
def fx(n): return open(os.path.join(FX, n), encoding="utf-8").read()

class ParsePtr(unittest.TestCase):
    def test_simple_filing(self):
        rows, exp = u.parse_ptr_text(fx("ptr_simple.txt"))
        self.assertEqual((len(rows), exp), (12, 12))
        r = rows[0]
        self.assertEqual((r["ticker"], r["asset"], r["assetType"], r["side"], r["amount"], r["tradeDate"], r["notified"]),
                         ("BRK.B", "Berkshire Hathaway Inc. New Common Stock", "ST", "buy", "$1,001 - $15,000", "2026-08-07", "2026-09-01"))
        self.assertEqual(rows[1]["amount"], "$15,001 - $50,000")           # amount wrapped onto the next line
        self.assertEqual(rows[2]["side"], "sell (partial)")
    def test_page_breaks_and_glued_entries_lose_nothing(self):
        rows, exp = u.parse_ptr_text(fx("ptr_pagebreaks.txt"))
        self.assertEqual(len(rows), exp)                                 # 78 asset codes, 78 rows
        self.assertTrue(all(r["owner"] == "dependent child" for r in rows))
        self.assertEqual(sum(1 for r in rows if r["ticker"] == "LYV"), 3)  # includes two LYV entries glued together by a page break
        self.assertEqual(sum(1 for r in rows if r["ticker"] == "CHRW"), 5) # one CHRW entry is split by the repeated table header
    def test_over_range_amounts(self):
        rows, exp = u.parse_ptr_text(fx("ptr_over_range.txt"))
        self.assertEqual(len(rows), exp)
        self.assertIn("Over $1,000,000", [r["amount"] for r in rows])
    def test_ticker_comes_from_the_asset_name_not_the_description(self):
        rows, exp = u.parse_ptr_text(fx("ptr_description_ticker.txt"))
        self.assertEqual(len(rows), exp)
        self.assertEqual({r["ticker"] for r in rows}, {"ACN", "MBGL", "SOLS"})  # description mentions SPGI; it must not win
    def test_scanned_filing_has_no_rows(self):
        self.assertEqual(u.parse_ptr_text("Filing ID #9116256\n\n\n"), ([], 0))

class SenateRows(unittest.TestCase):
    def test_senate_rows_from_community_dataset_are_filtered_and_labelled(self):
        today = dt.date(2026, 10, 16)
        lux = [{"chamber": "senate", "docId": "d1", "member": {"name": "Jane Roe", "state": "PA"}, "filedAt": "2026-09-01", "transactedAt": "2026-08-20",
                "ticker": "NVDA", "assetDescription": "NVIDIA", "assetType": "stock", "side": "buy", "amountRange": {"text": "$1,001 - $15,000"},
                "owner": "self", "provenance": {"sourceUrl": "https://efdsearch.senate.gov/search/view/ptr/d1/", "needsReview": False}},
               {"chamber": "house", "docId": "h", "member": {"name": "X"}, "filedAt": "2026-09-01"},
               {"chamber": "senate", "docId": "old", "member": {"name": "Old"}, "filedAt": "2025-01-01", "provenance": {}},
               {"chamber": "senate", "docId": "rev", "member": {"name": "Rev"}, "filedAt": "2026-09-01", "provenance": {"needsReview": True}}]
        import gzip
        orig = u.fetch
        def fake(url, **k):
            if url.endswith("snapshot-2026.json.gz"): return gzip.compress(json.dumps(lux).encode())
            if url.endswith("manifest.json"): return json.dumps({"datasets": {"congress-trades": {"lastIngestedAt": "2026-09-07T15:00:00Z"}}}).encode()
            raise u.urllib.error.HTTPError(url, 404, "nf", {}, None)
        u.fetch = fake
        try: rows, info = u.build_senate(today, 120, lambda s: None)
        finally: u.fetch = orig
        self.assertEqual([(r["p"], r["c"], r["t"], r["s"], r["o"]) for r in rows], [("Jane Roe", "Senate", "NVDA", "buy", "")])
        self.assertEqual((info["status"], info["asOf"]), ("ok", "2026-09-07"))
    def test_unavailable_dataset_yields_no_rows_not_an_exception(self):
        orig = u.fetch
        def boom(url, **k): raise OSError("down")
        u.fetch = boom
        try: rows, info = u.build_senate(dt.date(2026, 10, 16), 120, lambda s: None)
        finally: u.fetch = orig
        self.assertEqual((rows, info["status"]), ([], "unavailable"))

class ShippedFile(unittest.TestCase):
    def setUp(self): self.d = json.load(open(os.path.join(ROOT, "trades.json"), encoding="utf-8"))
    def test_schema_and_required_wording(self):
        d = self.d
        self.assertEqual(d["schema"], 1); self.assertIn("45 days", d["note"]); self.assertIn("Not investment advice", d["note"])
        self.assertTrue(d["generated"].endswith("Z")); self.assertGreater(len(d["trades"]), 100)
    def test_rows_are_well_formed(self):
        import re
        for t in self.d["trades"]:
            self.assertTrue(t["p"] and t["amt"], t)
            self.assertIn(t["s"], ("buy", "sell", "sell (partial)", "exchange"))
            self.assertTrue(re.fullmatch(r"\d{4}-\d\d-\d\d", t["td"]) and re.fullmatch(r"\d{4}-\d\d-\d\d", t["fd"]), t)
            self.assertIn(t["c"], ("House", "Senate"))
            if t["c"] == "Senate": self.assertTrue(t["u"].startswith("https://efdsearch.senate.gov/"), t)
            else: self.assertTrue(t["doc"], t)
    def test_never_sources_from_blocked_sites(self):
        text = json.dumps(self.d).lower()
        for bad in ("capitoltrades", "quiverquant", "unusualwhales"): self.assertNotIn(bad, text)
    def test_copies_identical_and_asset_types_cover_all_rows(self):
        a = open(os.path.join(ROOT, "trades.json"), "rb").read()
        for p in ("docs/trades.json", "android/app/src/main/assets/trades.json"): self.assertEqual(open(os.path.join(ROOT, p), "rb").read(), a, p)
        self.assertTrue({t["ty"] for t in self.d["trades"] if t["ty"]} <= set(self.d["assetTypes"]))
    def test_house_source_reports_unread_filings_honestly(self):
        h = next(s for s in self.d["sources"] if s["id"] == "house")
        self.assertEqual(h["filings"], h["filingsParsed"] + h["filingsNotRead"])

if __name__ == "__main__":
    unittest.main()
