package com.geek4945.mattytools.ui

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.browser.customtabs.CustomTabsIntent
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.geek4945.mattytools.data.Tool

val CATEGORY_EMOJI = mapOf(
    "ai" to "\uD83E\uDD16", "tv" to "\uD83D\uDCFA", "fun" to "\uD83C\uDFAE", "music" to "\uD83C\uDFA7",
    "design" to "\uD83C\uDFA8", "productivity" to "\uD83E\uDDF0", "learning" to "\uD83C\uDF93", "security" to "\uD83D\uDD12",
    "shopping" to "\uD83D\uDED2", "money" to "\uD83D\uDCBC", "lifestyle" to "\uD83C\uDF4E", "travel" to "\uD83D\uDDFA\uFE0F", "uncat" to "\u2728",
)

fun tagLabel(t: String) = t.replace('-', ' ').replaceFirstChar { it.uppercase() }

/** Opens the page in a Chrome Custom Tab (in-app browser); falls back to any browser. */
fun openUrl(ctx: Context, url: String) {
    val uri = Uri.parse(url)
    try {
        CustomTabsIntent.Builder().setShowTitle(true).build().launchUrl(ctx, uri)
    } catch (e: ActivityNotFoundException) {
        try { ctx.startActivity(Intent(Intent.ACTION_VIEW, uri).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) } catch (_: Exception) {}
    } catch (e: Exception) {
        try { ctx.startActivity(Intent(Intent.ACTION_VIEW, uri).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) } catch (_: Exception) {}
    }
}

fun shareTool(ctx: Context, t: Tool) {
    val text = buildString {
        append(t.name); if (t.description.isNotBlank()) append(" - ").append(t.description.take(140))
        append("\n").append(t.url)
        append("\n(found in Matty McTech's newsletter, via an unofficial fan-made directory)")
    }
    val i = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_SUBJECT, t.name).putExtra(Intent.EXTRA_TEXT, text)
    ctx.startActivity(Intent.createChooser(i, "Share ${t.name}").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
}

@Composable
fun NewBadge() {
    Surface(color = MaterialTheme.colorScheme.tertiary, shape = RoundedCornerShape(50)) {
        Text("NEW", modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
            style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.surface, fontWeight = FontWeight.Bold)
    }
}

@Composable
fun ToolCard(
    tool: Tool, categoryName: String?, isFavorite: Boolean, isNew: Boolean,
    onOpen: () -> Unit, onFavorite: () -> Unit, onShare: () -> Unit, onOpenPost: (String) -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onOpen),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        shape = RoundedCornerShape(16.dp),
    ) {
        Column(Modifier.padding(start = 16.dp, end = 8.dp, top = 12.dp, bottom = 8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(tool.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold,
                            maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f, fill = false))
                        if (isNew) NewBadge()
                    }
                    Text(tool.host, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary,
                        maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
                IconButton(onClick = onFavorite) {
                    Icon(if (isFavorite) Icons.Filled.Favorite else Icons.Filled.FavoriteBorder,
                        contentDescription = if (isFavorite) "Remove from favorites" else "Add to favorites",
                        tint = if (isFavorite) MaterialTheme.colorScheme.tertiary else MaterialTheme.colorScheme.onSurfaceVariant)
                }
                IconButton(onClick = onShare) { Icon(Icons.Filled.Share, contentDescription = "Share ${tool.name}", tint = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
            if (tool.description.isNotBlank()) {
                Spacer(Modifier.height(4.dp))
                Text(tool.description, style = MaterialTheme.typography.bodyMedium, maxLines = 4, overflow = TextOverflow.Ellipsis,
                    color = MaterialTheme.colorScheme.onSurface, modifier = Modifier.padding(end = 8.dp))
            }
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.padding(end = 8.dp)) {
                if (categoryName != null) SmallLabel(categoryName, primary = true)
                tool.tags.take(3).forEach { SmallLabel(tagLabel(it)) }
            }
            tool.sources.firstOrNull()?.let { s ->
                TextButton(onClick = { onOpenPost(s.url) }, contentPadding = PaddingValues(horizontal = 0.dp, vertical = 2.dp)) {
                    Text("From: ${s.title.trim()}" + if (s.date.isNotBlank()) " (${s.date})" else "", style = MaterialTheme.typography.labelSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
            }
        }
    }
}

@Composable
fun SmallLabel(text: String, primary: Boolean = false) {
    Surface(
        color = if (primary) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.background,
        shape = RoundedCornerShape(8.dp),
    ) {
        Text(text, modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp), style = MaterialTheme.typography.labelSmall,
            color = if (primary) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1)
    }
}

/** Horizontal row of "use" tag filter chips; tapping toggles the filter. */
@Composable
fun TagFilterRow(tags: List<String>, selected: Set<String>, onToggle: (String) -> Unit) {
    if (tags.isEmpty()) return
    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp), contentPadding = PaddingValues(horizontal = 16.dp)) {
        items(tags) { t ->
            FilterChip(selected = t in selected, onClick = { onToggle(t) }, label = { Text(tagLabel(t)) })
        }
    }
}
