package com.geek4945.mattytools

import com.geek4945.mattytools.data.*
import org.junit.Assert.*
import org.junit.Test
import java.io.File

class TradesTest {
    private val d = TradesJson.parse(File("src/main/assets/trades.json").readText())

    @Test fun bundledFileParsesWithBothChambersAndRequiredFields() {
        assertTrue(d.trades.size > 100)
        assertTrue(d.trades.any { it.chamber == "House" }); assertTrue(d.trades.any { it.chamber == "Senate" })
        assertTrue(d.generated.endsWith("Z")); assertTrue(d.note.contains("45 days"))
        for (t in d.trades) {
            assertTrue(t.politician.isNotBlank()); assertTrue(t.amount.isNotBlank())
            assertTrue(t.side in listOf("buy", "sell", "sell (partial)", "exchange"))
            assertTrue(Regex("""\d{4}-\d\d-\d\d""").matches(t.tradeDate)); assertTrue(Regex("""\d{4}-\d\d-\d\d""").matches(t.filedDate))
            assertNotNull("every row has a link to its filing", t.link)
        }
        assertTrue(d.sources.any { it.id == "house" && it.rows > 0 })
    }

    @Test fun houseLinksAreRebuiltAndOnlyHttpsIsAccepted() {
        val h = Trade("A B", "House", "TX01", "NVDA", "NVIDIA", "ST", "buy", "\$1,001 - \$15,000", "2026-08-01", "2026-09-01", "", "20035411", null)
        assertEquals("https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/20035411.pdf", h.link)
        assertNull(h.copy(chamber = "Senate").link)
        assertNull(h.copy(chamber = "Senate", url = "javascript:alert(1)").link)
        assertEquals("https://efdsearch.senate.gov/x", h.copy(chamber = "Senate", url = "https://efdsearch.senate.gov/x").link)
    }

    @Test fun filterByPoliticianTickerChamberAndSide() {
        val first = d.trades.first { it.ticker.isNotEmpty() }
        assertTrue(TradeFilter.apply(d.trades, first.ticker.lowercase(), null, SideFilter.ALL).all { it.ticker.lowercase().startsWith(first.ticker.lowercase()) || it.asset.lowercase().contains(first.ticker.lowercase()) || it.politician.lowercase().contains(first.ticker.lowercase()) })
        val last = first.politician.split(' ').last()
        assertTrue(TradeFilter.apply(d.trades, last, null, SideFilter.ALL).any { it.politician == first.politician })
        assertTrue(TradeFilter.apply(d.trades, "", "Senate", SideFilter.ALL).all { it.chamber == "Senate" })
        assertTrue(TradeFilter.apply(d.trades, "", null, SideFilter.BUY).all { it.isBuy })
        assertTrue(TradeFilter.apply(d.trades, "", null, SideFilter.SELL).all { it.isSell })
        assertEquals(d.trades.size, TradeFilter.apply(d.trades, "  ", null, SideFilter.ALL).size)
        assertTrue(TradeFilter.apply(d.trades, "zzzzqqq", null, SideFilter.ALL).isEmpty())
    }

    @Test fun rejectsFilesItDoesNotUnderstand() {
        assertThrows(Exception::class.java) { TradesJson.parse("{\"schema\":2,\"trades\":[]}") }
        assertThrows(Exception::class.java) { TradesJson.parse("not json") }
        assertThrows(Exception::class.java) { TradesJson.parse("{\"schema\":1}") }
    }

    @Test fun assetsCopyMatchesRepoRoot() {
        assertEquals(File("../../trades.json").readText(), File("src/main/assets/trades.json").readText())
    }
}
