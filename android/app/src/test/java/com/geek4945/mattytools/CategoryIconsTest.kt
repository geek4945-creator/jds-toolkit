package com.geek4945.mattytools

import com.geek4945.mattytools.data.*
import org.junit.Assert.*
import org.junit.Test
import java.io.File

class CategoryIconsTest {
    private val set = CategoryIconSet.parse(File("src/main/assets/icons.json").readText())
    private val catalog = CatalogJson.parse(File("src/main/assets/catalog.json").readText())

    @Test fun everyBundledCategoryHasItsOwnDistinctIcon() {
        assertTrue(catalog.categories.isNotEmpty())
        val names = catalog.categories.map { set.nameFor(it.id, it.icon) }
        assertEquals("each category should have a different icon", names.size, names.toSet().size)
        for (c in catalog.categories) {
            assertTrue("category ${c.id} has an icon field", c.icon.isNotEmpty())
            assertEquals(c.icon, set.nameFor(c.id))                 // catalog field and shared map agree
            assertTrue("${c.id} has artwork", set.pathsFor(c.id, c.icon).all { it.startsWith("M") || it.startsWith("m") } && set.pathsFor(c.id, c.icon).isNotEmpty())
        }
    }

    @Test fun unknownCategoryOrIconFallsBackToDefault() {
        assertEquals("folder", set.nameFor("brand-new-category"))
        assertEquals("folder", set.nameFor("brand-new-category", "no-such-icon"))
        assertEquals("palette", set.nameFor("design", "no-such-icon"))        // bad declared name -> id map
        assertEquals("palette", set.nameFor("brand-new-category", "palette")) // declared name wins for new categories
        assertTrue(set.pathsFor("brand-new-category").isNotEmpty())
    }

    @Test fun categoryIconFieldSurvivesJsonRoundTrip() {
        val back = CatalogJson.parse(CatalogJson.toJson(catalog))
        assertEquals(catalog.categories.map { it.icon }, back.categories.map { it.icon })
    }

    @Test fun iconFileIsIdenticalToTheRepoRootCopy() {
        assertEquals(File("../../icons.json").readText(), File("src/main/assets/icons.json").readText())
    }

    @Test fun everyIconPathParsesWithComposePathParser() {
        for ((name, paths) in set.icons) for (d in paths) {
            val nodes = androidx.compose.ui.graphics.vector.PathParser().parsePathString(d).toNodes()
            assertTrue("$name parses to nodes", nodes.size > 3)
        }
    }
}
