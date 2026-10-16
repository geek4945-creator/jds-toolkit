package com.geek4945.mattytools

import com.geek4945.mattytools.data.*
import org.junit.Assert.*
import org.junit.Test
import java.io.File

class CatalogTest {
    private fun tool(id: String, url: String, name: String = id, cat: String = "fun", desc: String = "d") =
        Tool(id, name, url, "h", desc, cat, listOf("free"), listOf(Source("P", "2026-01-01", "u", null)), null, 1, null)

    private fun cat(version: Int, vararg tools: Tool) = Catalog(version, "2026-01-01", listOf(Category("fun", "Fun", "")), tools.toList(), emptyList())

    @Test fun parsesBundledCatalogFile() {
        val f = File("src/main/assets/catalog.json")
        assertTrue("run from android/app, found ${f.absolutePath}", f.exists())
        val c = CatalogJson.parse(f.readText())
        assertTrue(c.version >= 1)
        assertTrue(c.tools.size > 50)
        assertTrue(c.tools.all { it.url.startsWith("http") && it.name.isNotEmpty() })
        assertEquals(c.tools.size, c.tools.map { it.id }.toSet().size)
        assertEquals(c.tools.size, c.categories.sumOf { c.countIn(it.id) })   // every tool sits in a known category
    }

    @Test fun jsonRoundTrip() {
        val c = cat(2, tool("a", "https://a.com"), tool("b", "https://b.com"))
        val back = CatalogJson.parse(CatalogJson.toJson(c))
        assertEquals(c.version, back.version)
        assertEquals(c.tools.map { it.id }, back.tools.map { it.id })
        assertEquals(c.tools[0].tags, back.tools[0].tags)
        assertEquals(c.tools[0].sources, back.tools[0].sources)
    }

    @Test fun urlKeyNormalises() {
        assertEquals("synthesia.io", urlKey("https://www.synthesia.io/?utm_source=chatgpt.com"))
        assertEquals("synthesia.io", urlKey("http://Synthesia.io/"))
        assertEquals("amazon.com/outlet", urlKey("https://www.amazon.com/Outlet"))
        assertEquals("x.com/a?q=1", urlKey("https://x.com/a/?utm_x=1&q=1"))
    }

    @Test fun mergeAddsNewToolsAndReportsThem() {
        val local = cat(1, tool("a", "https://a.com"))
        val remote = cat(2, tool("a", "https://a.com", desc = "updated"), tool("b", "https://b.com"), tool("c", "https://c.com"))
        val r = CatalogMerge.merge(local, remote)
        assertTrue(r.updated); assertEquals(2, r.catalog.version)
        assertEquals(listOf("b", "c"), r.newTools.map { it.id })
        assertEquals(3, r.catalog.tools.size)
        assertEquals("updated", r.catalog.tools.first { it.id == "a" }.description)
    }

    @Test fun mergeIgnoresSameOrOlderVersion() {
        val local = cat(3, tool("a", "https://a.com"))
        assertFalse(CatalogMerge.merge(local, cat(3, tool("z", "https://z.com"))).updated)
        val r = CatalogMerge.merge(local, cat(2, tool("z", "https://z.com")))
        assertFalse(r.updated); assertTrue(r.newTools.isEmpty()); assertEquals(1, r.catalog.tools.size)
    }

    @Test fun mergeMatchesByUrlWhenIdChanged() {
        val local = cat(1, tool("old-id", "https://www.a.com/"))
        val remote = cat(2, tool("new-id", "https://a.com"))
        val r = CatalogMerge.merge(local, remote)
        assertTrue(r.newTools.isEmpty()); assertEquals(1, r.catalog.tools.size); assertEquals("old-id", r.catalog.tools[0].id)
    }

    @Test fun mergeNeverDeletesLocalTools() {
        val local = cat(1, tool("a", "https://a.com"), tool("b", "https://b.com"))
        val r = CatalogMerge.merge(local, cat(2, tool("a", "https://a.com")))
        assertEquals(setOf("a", "b"), r.catalog.tools.map { it.id }.toSet())
    }

    @Test fun mergeKeepsFavoritesStableIds() {
        val local = cat(1, tool("a", "https://a.com"))
        val r = CatalogMerge.merge(local, cat(2, tool("a", "https://a.com", cat = "ai")))
        assertEquals("a", r.catalog.tools[0].id); assertEquals("ai", r.catalog.tools[0].category)
    }

    @Test fun sheetSourceWithBlankDateAndNewCategorySurviveUpdate() {
        val sheetTool = Tool("geoguessr-com", "Geo Guessr", "https://www.geoguessr.com/", "geoguessr.com", "Guess where", "live",
            listOf("cure-boredom"), listOf(Source("Sheet: Cure Boredom", "", "https://docs.google.com/spreadsheets/d/e/x/pubhtml", 1)), null, 2, "2026-11-01")
        val remote = Catalog(2, "2026-11-01", listOf(Category("fun", "Fun", ""), Category("live", "Live Maps & Trackers", "")), listOf(sheetTool), emptyList())
        val back = CatalogJson.parse(CatalogJson.toJson(remote))
        assertEquals("", back.tools[0].sources[0].date)
        val r = CatalogMerge.merge(cat(1, tool("a", "https://a.com")), back)
        assertTrue(r.updated)
        assertEquals(listOf("geoguessr-com"), r.newTools.map { it.id })
        assertNotNull(r.catalog.category("live"))
        assertEquals(2, r.catalog.tools.size)
    }
}
