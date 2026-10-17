package com.geek4945.mattytools.data

import org.json.JSONObject

/** One disclosed transaction, as filed (public STOCK Act disclosures). Compact keys match trades.json. */
data class Trade(
    val politician: String, val chamber: String, val state: String, val ticker: String, val asset: String, val assetType: String,
    val side: String, val amount: String, val tradeDate: String, val filedDate: String, val owner: String, val doc: String, val url: String?,
) {
    /** Link to the filing: Senate rows carry one; House rows are rebuilt from the document id and filing year. */
    val link: String? get() = url?.takeIf { it.startsWith("https://") }
        ?: if (chamber == "House" && doc.isNotEmpty() && filedDate.length >= 4)
            "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/${filedDate.substring(0, 4)}/$doc.pdf" else null
    val isBuy get() = side == "buy"
    val isSell get() = side.startsWith("sell")
}

data class TradeSource(val id: String, val name: String, val url: String, val status: String, val rows: Int, val asOf: String, val notRead: Int)

data class TradesData(
    val generated: String, val windowDays: Int, val note: String, val sources: List<TradeSource>,
    val assetTypes: Map<String, String>, val trades: List<Trade>,
) {
    val latestFiling: String get() = trades.maxOfOrNull { it.filedDate } ?: ""
    fun typeLabel(code: String) = assetTypes[code] ?: code
}

object TradesJson {
    private fun JSONObject.str(k: String) = if (has(k) && !isNull(k)) optString(k) else ""

    /** Throws if the text is not a trades.json this app understands (schema 1 with a trades array). */
    fun parse(text: String): TradesData {
        val o = JSONObject(text)
        require(o.optInt("schema", 0) == 1) { "unsupported trades schema" }
        val arr = o.getJSONArray("trades")
        val trades = (0 until arr.length()).mapNotNull { i ->
            val t = arr.getJSONObject(i)
            val p = t.str("p"); if (p.isEmpty()) return@mapNotNull null
            Trade(p, t.str("c"), t.str("st"), t.str("t"), t.str("a"), t.str("ty"), t.str("s"), t.str("amt"),
                t.str("td"), t.str("fd"), t.str("o"), t.str("doc"), t.str("u").ifEmpty { null })
        }
        val src = o.optJSONArray("sources")?.let { a ->
            (0 until a.length()).map { i ->
                a.getJSONObject(i).let { s ->
                    TradeSource(s.str("id"), s.str("name"), s.str("url").ifEmpty { s.str("official") }, s.str("status"), s.optInt("rows"), s.str("asOf"),
                        s.optInt("filingsNotRead"))
                }
            }
        } ?: emptyList()
        val types = o.optJSONObject("assetTypes")?.let { a -> a.keys().asSequence().associateWith { a.getString(it) } } ?: emptyMap()
        return TradesData(o.str("generated"), o.optInt("windowDays"), o.str("note"), src, types, trades)
    }
}

enum class SideFilter { ALL, BUY, SELL }

object TradeFilter {
    /** Filter by free text (politician, ticker or asset name; every word must match), chamber ("House"/"Senate"/null) and buy/sell. */
    fun apply(rows: List<Trade>, query: String, chamber: String?, side: SideFilter): List<Trade> {
        val words = query.trim().lowercase().split(' ').filter { it.isNotEmpty() }
        return rows.filter { t ->
            (chamber == null || t.chamber == chamber) &&
                (side == SideFilter.ALL || (side == SideFilter.BUY && t.isBuy) || (side == SideFilter.SELL && t.isSell)) &&
                words.all { w -> t.politician.lowercase().contains(w) || t.ticker.lowercase() == w || t.ticker.lowercase().startsWith(w) || t.asset.lowercase().contains(w) }
        }
    }
}
