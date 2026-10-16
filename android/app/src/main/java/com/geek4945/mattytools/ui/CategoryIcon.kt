package com.geek4945.mattytools.ui

import android.content.Context
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.geek4945.mattytools.data.Category
import com.geek4945.mattytools.data.CategoryIconSet

private object IconStore {
    @Volatile private var set: CategoryIconSet? = null
    private val cache = HashMap<String, ImageVector>()

    fun get(ctx: Context): CategoryIconSet = set ?: synchronized(this) {
        set ?: try {
            ctx.applicationContext.assets.open("icons.json").bufferedReader().use { CategoryIconSet.parse(it.readText()) }
        } catch (_: Exception) { CategoryIconSet.EMPTY }.also { set = it }
    }

    @Synchronized fun vector(name: String, paths: List<String>): ImageVector = cache.getOrPut(name) {
        ImageVector.Builder(name, 24.dp, 24.dp, 24f, 24f).apply {
            for (d in paths) addPath(PathParser().parsePathString(d).toNodes(), fill = SolidColor(Color.Black))
        }.build()
    }
}

/** The icon for a category (own `icon` field, else the shared id map, else the default folder icon). Tinted by the theme. */
@Composable
fun CategoryGlyph(category: Category, tint: Color, modifier: Modifier = Modifier, size: Dp = 24.dp) {
    val ctx = LocalContext.current
    val vec = remember(category.id, category.icon) {
        val set = IconStore.get(ctx)
        val name = set.nameFor(category.id, category.icon)
        set.icons[name]?.takeIf { it.isNotEmpty() }?.let { IconStore.vector(name, it) }
    } ?: return
    Icon(vec, contentDescription = null, tint = tint, modifier = modifier.size(size))
}

/** Rounded tinted tile holding the category icon: big on the home cards, small on category screens. */
@Composable
fun CategoryBadge(category: Category, tile: Dp = 52.dp, glyph: Dp = 28.dp) {
    Surface(color = MaterialTheme.colorScheme.primaryContainer, shape = RoundedCornerShape(tile / 3.2f), modifier = Modifier.size(tile)) {
        androidx.compose.foundation.layout.Box(contentAlignment = Alignment.Center) {
            CategoryGlyph(category, MaterialTheme.colorScheme.onPrimaryContainer, size = glyph)
        }
    }
}
