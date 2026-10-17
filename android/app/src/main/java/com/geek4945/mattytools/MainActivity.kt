package com.geek4945.mattytools

import android.net.Uri
import android.Manifest
import android.content.Intent
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.geek4945.mattytools.data.*
import com.geek4945.mattytools.ui.*
import kotlinx.coroutines.launch
import java.text.DateFormat
import java.util.Date

sealed interface Screen {
    data object Home : Screen
    data class CategoryScreen(val id: String) : Screen
    data object Search : Screen
    data object Favorites : Screen
    data object NewItems : Screen
    data object Settings : Screen
    data object About : Screen
    data object Trades : Screen
}

class MainActivity : ComponentActivity() {
    private var showNewRequest by mutableStateOf(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        showNewRequest = intent?.getBooleanExtra("show_new", false) == true
        val repo = (application as ToolsApp).repo
        setContent {
            val theme by repo.theme.collectAsStateWithLifecycle()
            MattyTheme(theme) { AppRoot(repo, showNewRequest) { showNewRequest = false } }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        if (intent.getBooleanExtra("show_new", false)) showNewRequest = true
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppRoot(repo: CatalogRepository, showNew: Boolean, onShowNewHandled: () -> Unit) {
    val ctx = LocalContext.current
    val catalog by repo.catalog.collectAsStateWithLifecycle()
    val favorites by repo.favorites.collectAsStateWithLifecycle()
    val recents by repo.recents.collectAsStateWithLifecycle()
    val newIds by repo.newIds.collectAsStateWithLifecycle()

    val stack = remember { mutableStateListOf<Screen>(Screen.Home) }
    val current = stack.last()
    fun go(s: Screen) { if (stack.last() != s) stack.add(s) }
    fun goRoot(s: Screen) { stack.clear(); stack.add(s) }
    LaunchedEffect(showNew) { if (showNew) { goRoot(Screen.Home); go(Screen.NewItems); onShowNewHandled() } }
    BackHandler(enabled = stack.size > 1) { stack.removeAt(stack.lastIndex) }

    val toolById = remember(catalog) { catalog.tools.associateBy { it.id } }
    fun open(t: Tool) { repo.markOpened(t.id); openUrl(ctx, t.url) }
    val actions = ToolActions(
        isFavorite = { it in favorites }, isNew = { it in newIds },
        categoryName = { id -> catalog.category(id)?.name ?: "Uncategorized" },
        open = ::open, toggleFavorite = { repo.toggleFavorite(it.id) }, share = { shareTool(ctx, it) },
        openPost = { openUrl(ctx, it) },
    )

    val rootScreens = listOf(Screen.Home, Screen.Search, Screen.Favorites, Screen.Settings)
    val atRoot = stack.size == 1 || current in rootScreens && stack.size <= 2

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        when (current) {
                            Screen.Home -> "JD's Toolkit"
                            is Screen.CategoryScreen -> catalog.category(current.id)?.name ?: "Category"
                            Screen.Search -> "Search"
                            Screen.Favorites -> "Favorites & recent"
                            Screen.NewItems -> "New tools"
                            Screen.Settings -> "Settings"
                            Screen.About -> "About"
                            Screen.Trades -> "Politician Trades"
                        }, maxLines = 1, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.SemiBold,
                    )
                },
                navigationIcon = {
                    if (stack.size > 1) IconButton(onClick = { stack.removeAt(stack.lastIndex) }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    if (current == Screen.Home) IconButton(onClick = { go(Screen.About) }) { Icon(Icons.Filled.Info, contentDescription = "About") }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
            )
        },
        bottomBar = {
            NavigationBar(containerColor = MaterialTheme.colorScheme.surfaceVariant) {
                val rootOf = stack.first()
                NavigationBarItem(selected = rootOf == Screen.Home, onClick = { goRoot(Screen.Home) }, icon = { Icon(Icons.Filled.Home, null) }, label = { Text("Home") })
                NavigationBarItem(selected = rootOf == Screen.Search, onClick = { goRoot(Screen.Search) }, icon = { Icon(Icons.Filled.Search, null) }, label = { Text("Search") })
                NavigationBarItem(selected = rootOf == Screen.Favorites, onClick = { goRoot(Screen.Favorites) }, icon = { Icon(Icons.Filled.Favorite, null) }, label = { Text("Saved") })
                NavigationBarItem(selected = rootOf == Screen.Settings, onClick = { goRoot(Screen.Settings) }, icon = { Icon(Icons.Filled.Settings, null) }, label = { Text("Settings") })
            }
        },
    ) { pad ->
        Box(Modifier.padding(pad).fillMaxSize()) {
            when (val s = current) {
                Screen.Home -> HomeScreen(catalog, recents.mapNotNull { toolById[it] }.take(8), newIds.keys.mapNotNull { toolById[it] },
                    onCategory = { go(Screen.CategoryScreen(it)) }, onSearch = { goRoot(Screen.Search) },
                    onSeeNew = { go(Screen.NewItems) }, actions = actions)
                is Screen.CategoryScreen -> ToolListScreen(
                    tools = catalog.tools.filter { it.category == s.id }.sortedBy { it.name.lowercase() },
                    actions = actions, header = catalog.category(s.id)?.blurb ?: "", category = catalog.category(s.id),
                    top = if (s.id == "money") ({ TradesFeatureCard { go(Screen.Trades) } }) else null)
                Screen.Trades -> TradesScreen(repo.tradesStore)
                Screen.Search -> SearchScreen(catalog, actions)
                Screen.Favorites -> SavedScreen(favorites.mapNotNull { toolById[it] }, recents.mapNotNull { toolById[it] }, actions)
                Screen.NewItems -> NewScreen(newIds.keys.mapNotNull { toolById[it] }, actions) { repo.clearNew() }
                Screen.Settings -> SettingsScreen(repo, catalog, onAbout = { go(Screen.About) })
                Screen.About -> AboutScreen(catalog)
            }
        }
    }
}

class ToolActions(
    val isFavorite: (String) -> Boolean, val isNew: (String) -> Boolean, val categoryName: (String) -> String,
    val open: (Tool) -> Unit, val toggleFavorite: (Tool) -> Unit, val share: (Tool) -> Unit, val openPost: (String) -> Unit,
)

@Composable
fun ToolCardFor(t: Tool, a: ToolActions, showCategory: Boolean = true) {
    ToolCard(t, if (showCategory) a.categoryName(t.category) else null, a.isFavorite(t.id), a.isNew(t.id),
        onOpen = { a.open(t) }, onFavorite = { a.toggleFavorite(t) }, onShare = { a.share(t) }, onOpenPost = a.openPost)
}

@Composable
fun HomeScreen(
    catalog: Catalog, recents: List<Tool>, newTools: List<Tool>,
    onCategory: (String) -> Unit, onSearch: () -> Unit, onSeeNew: () -> Unit, actions: ToolActions,
) {
    val cats = catalog.categories.filter { catalog.countIn(it.id) > 0 }
    LazyVerticalGrid(
        columns = GridCells.Fixed(2), contentPadding = PaddingValues(16.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp), verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item(span = { androidx.compose.foundation.lazy.grid.GridItemSpan(2) }) {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Surface(
                    onClick = onSearch, shape = RoundedCornerShape(28.dp), color = MaterialTheme.colorScheme.surfaceVariant,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Row(Modifier.padding(horizontal = 18.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Filled.Search, null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(Modifier.width(12.dp))
                        Text("Search ${catalog.tools.size} tools & sites", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                Text(
                    "Handy tools and sites, sorted by what they're for.",
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (newTools.isNotEmpty()) {
                    Card(
                        onClick = onSeeNew, shape = RoundedCornerShape(16.dp),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                            NewBadge(); Spacer(Modifier.width(12.dp))
                            Text("${newTools.size} new tool${if (newTools.size == 1) "" else "s"} added - tap to see",
                                color = MaterialTheme.colorScheme.onPrimaryContainer, fontWeight = FontWeight.Medium)
                        }
                    }
                }
                Text("Categories", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            }
        }
        items(cats, key = { it.id }) { c ->
            val newInCat = newTools.count { it.category == c.id }
            Card(
                onClick = { onCategory(c.id) }, shape = RoundedCornerShape(20.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                modifier = Modifier.fillMaxWidth().heightIn(min = 132.dp),
            ) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        CategoryBadge(c)
                        Spacer(Modifier.weight(1f))
                        if (newInCat > 0) NewBadge()
                    }
                    Text(c.name, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold, maxLines = 2)
                    Text("${catalog.countIn(c.id)} tools", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
                }
            }
        }
        if (recents.isNotEmpty()) {
            item(span = { androidx.compose.foundation.lazy.grid.GridItemSpan(2) }) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Spacer(Modifier.height(4.dp))
                    Text("Recently opened", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(recents, key = { it.id }) { t ->
                            AssistChip(onClick = { actions.open(t) }, label = { Text(t.name, maxLines = 1) })
                        }
                    }
                }
            }
        }
    }
}

/** Reusable list with the "use" tag filter on top. */
@Composable
fun ToolListScreen(tools: List<Tool>, actions: ToolActions, header: String = "", emptyText: String = "Nothing here yet.", category: Category? = null, top: (@Composable () -> Unit)? = null) {
    var selected by rememberSaveable { mutableStateOf(setOf<String>()) }
    val tags = remember(tools) { tools.flatMap { it.tags }.groupingBy { it }.eachCount().entries.sortedByDescending { it.value }.map { it.key } }
    val shown = tools.filter { t -> selected.all { it in t.tags } }
    LazyColumn(contentPadding = PaddingValues(bottom = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        if (top != null) item { Box(Modifier.padding(horizontal = 16.dp)) { top() } }
        if (category != null) item {
            Row(Modifier.padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                CategoryBadge(category, tile = 40.dp, glyph = 22.dp)
                if (header.isNotBlank()) Text(header, Modifier.weight(1f), color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        } else if (header.isNotBlank()) item { Text(header, Modifier.padding(horizontal = 16.dp), color = MaterialTheme.colorScheme.onSurfaceVariant) }
        if (tags.isNotEmpty()) item { TagFilterRow(tags, selected) { t -> selected = if (t in selected) selected - t else selected + t } }
        if (shown.isEmpty()) item { Text(emptyText, Modifier.padding(24.dp).fillMaxWidth(), textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        items(shown, key = { it.id }) { t -> Box(Modifier.padding(horizontal = 16.dp)) { ToolCardFor(t, actions, showCategory = false) } }
    }
}

@Composable
fun SearchScreen(catalog: Catalog, actions: ToolActions) {
    var query by rememberSaveable { mutableStateOf("") }
    var selected by rememberSaveable { mutableStateOf(setOf<String>()) }
    val tags = remember(catalog) { catalog.allTags.take(24) }
    val q = query.trim().lowercase()
    val results = remember(catalog, q, selected) {
        catalog.tools.filter { t ->
            selected.all { it in t.tags } && (q.isEmpty() || q.split(' ').filter { it.isNotEmpty() }.all { w ->
                t.name.lowercase().contains(w) || t.description.lowercase().contains(w) || t.host.lowercase().contains(w) ||
                    t.tags.any { it.replace('-', ' ').contains(w) } || (catalog.category(t.category)?.name?.lowercase()?.contains(w) == true)
            })
        }.sortedBy { it.name.lowercase() }
    }
    Column {
        OutlinedTextField(
            value = query, onValueChange = { query = it }, singleLine = true, placeholder = { Text("Search name, use, site...") },
            leadingIcon = { Icon(Icons.Filled.Search, null) },
            trailingIcon = { if (query.isNotEmpty()) IconButton(onClick = { query = "" }) { Icon(Icons.Filled.Close, "Clear") } },
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search), shape = RoundedCornerShape(28.dp),
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
        )
        TagFilterRow(tags, selected) { t -> selected = if (t in selected) selected - t else selected + t }
        Text("${results.size} result${if (results.size == 1) "" else "s"}", Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
            style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        LazyColumn(contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            items(results, key = { it.id }) { ToolCardFor(it, actions) }
        }
    }
}

@Composable
fun SavedScreen(favs: List<Tool>, recents: List<Tool>, actions: ToolActions) {
    var tab by rememberSaveable { mutableIntStateOf(0) }
    Column {
        TabRow(selectedTabIndex = tab, containerColor = MaterialTheme.colorScheme.background) {
            Tab(selected = tab == 0, onClick = { tab = 0 }, text = { Text("Favorites (${favs.size})") })
            Tab(selected = tab == 1, onClick = { tab = 1 }, text = { Text("Recently opened") })
        }
        val list = if (tab == 0) favs else recents
        if (list.isEmpty()) {
            Text(if (tab == 0) "Tap the heart on any tool to keep it here." else "Tools you open will show up here.",
                Modifier.padding(32.dp).fillMaxWidth(), textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            items(list, key = { it.id }) { ToolCardFor(it, actions) }
        }
    }
}

@Composable
fun NewScreen(tools: List<Tool>, actions: ToolActions, onClear: () -> Unit) {
    LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(if (tools.isEmpty()) "No new tools right now. They appear here after a monthly update." else "Added in recent updates",
                    Modifier.weight(1f), color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (tools.isNotEmpty()) TextButton(onClick = onClear) { Text("Mark all seen") }
            }
        }
        items(tools, key = { it.id }) { ToolCardFor(it, actions) }
    }
}

@Composable
fun SettingsScreen(repo: CatalogRepository, catalog: Catalog, onAbout: () -> Unit) {
    val scope = rememberCoroutineScope()
    val theme by repo.theme.collectAsStateWithLifecycle()
    val last by repo.lastChecked.collectAsStateWithLifecycle()
    val lastMsg by repo.lastResult.collectAsStateWithLifecycle()
    val notify by repo.notify.collectAsStateWithLifecycle()
    var busy by remember { mutableStateOf(false) }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { }
    val df = remember { DateFormat.getDateTimeInstance(DateFormat.MEDIUM, DateFormat.SHORT) }

    LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item { SectionTitle("Theme") }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                ThemeMode.entries.forEach { m ->
                    FilterChip(selected = theme == m, onClick = { repo.setTheme(m) },
                        label = { Text(m.name.lowercase().replaceFirstChar { it.uppercase() }) })
                }
            }
        }
        item { SectionTitle("Catalog updates") }
        item {
            Card(shape = RoundedCornerShape(16.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Catalog version ${catalog.version} (${catalog.date}), ${catalog.tools.size} tools", fontWeight = FontWeight.Medium)
                    Text("The app checks for new tools about once a month in the background (when you have a network connection).",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("Last checked: " + if (last == 0L) "never" else df.format(Date(last)), style = MaterialTheme.typography.bodyMedium)
                    if (lastMsg.isNotBlank()) Text(lastMsg, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
                    Button(onClick = { scope.launch { busy = true; repo.checkForUpdates(); busy = false } }, enabled = !busy) {
                        if (busy) CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp, color = MaterialTheme.colorScheme.onPrimary)
                        else Icon(Icons.Filled.Refresh, null)
                        Spacer(Modifier.width(8.dp)); Text(if (busy) "Checking..." else "Check for updates now")
                    }
                }
            }
        }
        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Notify me about new tools", fontWeight = FontWeight.Medium)
                    Text("A notification like \"3 new tools added\" after a monthly update", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Switch(checked = notify, onCheckedChange = {
                    repo.setNotify(it)
                    if (it && Build.VERSION.SDK_INT >= 33) permission.launch(Manifest.permission.POST_NOTIFICATIONS)
                })
            }
        }
        item { SectionTitle("More") }
        item { OutlinedButton(onClick = onAbout, modifier = Modifier.fillMaxWidth()) { Icon(Icons.Filled.Info, null); Spacer(Modifier.width(8.dp)); Text("About JD's Toolkit") } }
    }
}

@Composable
fun SectionTitle(t: String) = Text(t, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)

@Composable
fun AboutScreen(catalog: Catalog) {
    val ctx = LocalContext.current
    LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item {
            Card(shape = RoundedCornerShape(16.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.tertiary.copy(alpha = 0.15f))) {
                Column(Modifier.padding(16.dp)) {
                    Text("Unofficial, fan-made toolkit", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(6.dp))
                    Text("JD's Toolkit is an independent, fan-made index. It is NOT made by, affiliated with, or endorsed by the people or sites credited below or the tools it links to.")
                }
            }
        }
        item { Text("Credits", fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.titleMedium) }
        items(catalog.credits.size) { i ->
            val c = catalog.credits[i]
            Card(shape = RoundedCornerShape(16.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
                Column(Modifier.padding(16.dp)) {
                    Text(c.name, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleSmall)
                    Spacer(Modifier.height(4.dp))
                    Text(c.contribution)
                    if (c.url != null) {
                        Spacer(Modifier.height(8.dp))
                        OutlinedButton(onClick = { openUrl(ctx, c.url) }, modifier = Modifier.fillMaxWidth()) { Text("Open ${Uri.parse(c.url).host?.removePrefix("www.") ?: "link"}") }
                    }
                }
            }
        }
        item {
            Text("Each tool also shows where it came from on its \"From:\" line. Thank you to everyone who shares good finds.",
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        item {
            Text("What is in the list", fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(4.dp))
            Text("Catalog v${catalog.version} (${catalog.date}): ${catalog.tools.size} tools. " +
                "Only openly readable parts of sources are listed (nothing behind a sign-up or paywall). " +
                "Categories and tags are assigned automatically from keywords, so a few may be off.")
        }
        item {
            Text("Privacy", fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(4.dp))
            Text("No account, no ads, no analytics. Favorites and history stay on your phone. The only network requests the app makes itself are downloading the public catalog file from GitHub and, when you open Politician Trades, the public trades list from the same repository.")
        }
        item { OutlinedButton(onClick = { openUrl(ctx, BuildConfig.REPO_URL) }, modifier = Modifier.fillMaxWidth()) { Text("Project page on GitHub") } }
        item { Text("Version ${BuildConfig.VERSION_NAME}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    }
}
