package com.geek4945.mattytools.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.geek4945.mattytools.data.*
import kotlinx.coroutines.launch
import java.text.DateFormat
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.TimeZone

/** Outside sites we only link to (never fetch): they block bots and have their own terms. */
val TRADE_LINKS = listOf(
    Triple("Capitol Trades", "https://www.capitoltrades.com/", "Browse by politician, company and date"),
    Triple("Quiver Quantitative: Congress Trading", "https://www.quiverquant.com/congresstrading/", "Charts of reported trades; some features paid"),
    Triple("Unusual Whales: Politician Trading", "https://unusualwhales.com/politics", "Trades by politician; some data paid"),
    Triple("House Financial Disclosures (official)", "https://disclosures-clerk.house.gov/FinancialDisclosure", "The original House filings"),
    Triple("Senate Financial Disclosures (official)", "https://efdsearch.senate.gov/search/home/", "The original Senate filings"),
)

fun formatStamp(iso: String): String = try {
    val p = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") }.parse(iso)!!
    DateFormat.getDateTimeInstance(DateFormat.MEDIUM, DateFormat.SHORT).format(p)
} catch (_: Exception) { iso }

/** Entry card shown at the top of Money, Jobs & Business. */
@Composable
fun TradesFeatureCard(onClick: () -> Unit) {
    Card(
        onClick = onClick, shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Politician Trades digest", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onPrimaryContainer)
            Text("Recent stock trades reported by members of Congress in their public STOCK Act disclosures. Search by name or ticker.",
                color = MaterialTheme.colorScheme.onPrimaryContainer, style = MaterialTheme.typography.bodyMedium)
            Text("Open the digest", color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.labelLarge)
        }
    }
}

@Composable
fun TradesScreen(store: TradesStore) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    val data by store.data.collectAsStateWithLifecycle()
    val status by store.status.collectAsStateWithLifecycle()
    var query by rememberSaveable { mutableStateOf("") }
    var chamber by rememberSaveable { mutableStateOf<String?>(null) }
    var side by rememberSaveable { mutableStateOf(SideFilter.ALL) }
    var busy by remember { mutableStateOf(false) }
    fun refresh() { scope.launch { busy = true; store.refresh(); busy = false } }
    LaunchedEffect(Unit) { refresh() }   // pick up the newest published list when the screen opens (one small file, no key)

    val all = data?.trades ?: emptyList()
    val rows = remember(all, query, chamber, side) { TradeFilter.apply(all, query, chamber, side) }

    LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Card(shape = RoundedCornerShape(16.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Politician Trades", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Text("Stock trades that U.S. House members and senators have reported in public STOCK Act disclosures, shown as filed. " +
                        "This is information, not investment advice, and a trade appearing here does not say why it was made.")
                    Text("Filings can be made up to 45 days after a trade, so recent trades may be missing. Amounts are ranges, not exact values.",
                        fontWeight = FontWeight.Medium)
                    val d = data
                    if (d != null) {
                        Text("List refreshed ${formatStamp(d.generated)} \u00B7 latest filing ${d.latestFiling} \u00B7 last ${d.windowDays} days \u00B7 ${d.trades.size} trades",
                            style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        d.sources.forEach { s ->
                            val extra = buildString {
                                append("${s.rows} trades")
                                if (s.asOf.isNotEmpty()) append(", data as of ${s.asOf}")
                                if (s.notRead > 0) append(", ${s.notRead} scanned/paper filings not shown")
                                if (s.status != "ok") append(" (${s.status})")
                            }
                            Text("\u2022 ${s.name}: $extra", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    } else Text("No saved list found. Tap Refresh when you are online.", color = MaterialTheme.colorScheme.error)
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        OutlinedButton(onClick = { refresh() }, enabled = !busy) {
                            Icon(Icons.Filled.Refresh, null); Spacer(Modifier.width(6.dp)); Text(if (busy) "Refreshing..." else "Refresh")
                        }
                        Spacer(Modifier.width(10.dp))
                        if (status.isNotEmpty()) Text(status, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.weight(1f))
                    }
                }
            }
        }
        item {
            OutlinedTextField(
                value = query, onValueChange = { query = it }, singleLine = true, placeholder = { Text("Politician, ticker or company") },
                leadingIcon = { Icon(Icons.Filled.Search, null) },
                trailingIcon = { if (query.isNotEmpty()) IconButton(onClick = { query = "" }) { Icon(Icons.Filled.Close, "Clear") } },
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search), shape = RoundedCornerShape(28.dp), modifier = Modifier.fillMaxWidth(),
            )
        }
        item {
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                item { FilterChip(selected = chamber == null, onClick = { chamber = null }, label = { Text("Both chambers") }) }
                item { FilterChip(selected = chamber == "House", onClick = { chamber = if (chamber == "House") null else "House" }, label = { Text("House") }) }
                item { FilterChip(selected = chamber == "Senate", onClick = { chamber = if (chamber == "Senate") null else "Senate" }, label = { Text("Senate") }) }
                item { FilterChip(selected = side == SideFilter.BUY, onClick = { side = if (side == SideFilter.BUY) SideFilter.ALL else SideFilter.BUY }, label = { Text("Buys") }) }
                item { FilterChip(selected = side == SideFilter.SELL, onClick = { side = if (side == SideFilter.SELL) SideFilter.ALL else SideFilter.SELL }, label = { Text("Sells") }) }
            }
        }
        item { Text("${rows.size} trade${if (rows.size == 1) "" else "s"}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        if (rows.isEmpty() && data != null) item { Text("No trades match. Try a shorter name or a ticker like NVDA.", color = MaterialTheme.colorScheme.onSurfaceVariant) }
        items(rows.take(300)) { t -> TradeCard(t, data?.typeLabel(t.assetType) ?: "") { t.link?.let { u -> openUrl(ctx, u) } } }
        if (rows.size > 300) item { Text("Showing the newest 300. Narrow the search to see more.", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        item { Spacer(Modifier.height(6.dp)); Text("More places to look", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold) }
        item { Text("These sites have their own terms and may block automated access, so JD's Toolkit only links to them.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        items(TRADE_LINKS) { (name, url, what) ->
            OutlinedButton(onClick = { openUrl(ctx, url) }, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(14.dp)) {
                Column(Modifier.weight(1f)) { Text(name, fontWeight = FontWeight.SemiBold); Text(what, style = MaterialTheme.typography.labelSmall) }
            }
        }
        item {
            Text(data?.note ?: "", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun TradeCard(t: Trade, typeLabel: String, onOpen: () -> Unit) {
    Card(
        onClick = onOpen, enabled = t.link != null, shape = RoundedCornerShape(14.dp), modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(t.politician, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis)
                val verb = t.side.replaceFirstChar { it.uppercase() }
                Surface(color = if (t.isBuy) MaterialTheme.colorScheme.secondaryContainer else if (t.isSell) MaterialTheme.colorScheme.tertiary.copy(alpha = 0.18f) else MaterialTheme.colorScheme.background,
                    shape = RoundedCornerShape(8.dp)) {
                    Text(verb, Modifier.padding(horizontal = 8.dp, vertical = 3.dp), style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
                }
            }
            Text("${t.chamber}${if (t.state.isNotEmpty()) " \u00B7 ${t.state}" else ""}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
            Text(buildString { if (t.ticker.isNotEmpty()) append(t.ticker).append("  \u2014  "); append(t.asset) }, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Text(t.amount, fontWeight = FontWeight.Medium)
            Text(buildString {
                append("Traded ${t.tradeDate} \u00B7 Filed ${t.filedDate}")
                if (t.owner.isNotEmpty()) append(" \u00B7 ${t.owner}")
                if (typeLabel.isNotEmpty() && typeLabel != "Stock") append(" \u00B7 $typeLabel")
            }, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
