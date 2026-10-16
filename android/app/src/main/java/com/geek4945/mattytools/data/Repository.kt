package com.geek4945.mattytools.data

import android.content.Context
import android.content.SharedPreferences
import com.geek4945.mattytools.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

sealed interface UpdateResult {
    data class Updated(val newCount: Int, val version: Int) : UpdateResult
    data class UpToDate(val version: Int) : UpdateResult
    data class Failed(val message: String) : UpdateResult
}

enum class ThemeMode { SYSTEM, LIGHT, DARK }

/** Holds the catalog (bundled asset, replaced by a downloaded newer copy) and the user's state. */
class CatalogRepository(private val ctx: Context) {
    private val prefs: SharedPreferences = ctx.getSharedPreferences("matty_tools", Context.MODE_PRIVATE)
    private val file = File(ctx.filesDir, "catalog.json")
    private val lock = Mutex()

    private val _catalog = MutableStateFlow(loadCatalog())
    val catalog: StateFlow<Catalog> = _catalog

    private val _favorites = MutableStateFlow(prefs.getStringSet("favorites", emptySet())!!.toSet())
    val favorites: StateFlow<Set<String>> = _favorites

    private val _recents = MutableStateFlow(prefs.getString("recents", "")!!.split(',').filter { it.isNotEmpty() })
    val recents: StateFlow<List<String>> = _recents

    /** id -> epoch millis when it was merged in as new. Cleared when opened or after 30 days. */
    private val _newIds = MutableStateFlow(readNew())
    val newIds: StateFlow<Map<String, Long>> = _newIds

    private val _lastChecked = MutableStateFlow(prefs.getLong("lastChecked", 0L))
    val lastChecked: StateFlow<Long> = _lastChecked
    private val _lastResult = MutableStateFlow(prefs.getString("lastResult", "") ?: "")
    val lastResult: StateFlow<String> = _lastResult

    private val _theme = MutableStateFlow(ThemeMode.valueOf(prefs.getString("theme", ThemeMode.SYSTEM.name)!!))
    val theme: StateFlow<ThemeMode> = _theme

    private val _notify = MutableStateFlow(prefs.getBoolean("notify", true))
    val notify: StateFlow<Boolean> = _notify

    private fun bundled(): Catalog = ctx.assets.open("catalog.json").bufferedReader().use { CatalogJson.parse(it.readText()) }

    private fun loadCatalog(): Catalog {
        val b = bundled()
        if (file.exists()) {
            try {
                val d = CatalogJson.parse(file.readText())
                // A newer app build may ship a newer bundled catalog; use whichever is newer.
                // Catalogs saved by older app versions have no credits: fall back to the bundled list.
                if (d.version >= b.version) return if (d.credits.isEmpty()) d.copy(credits = b.credits) else d
            } catch (_: Exception) { /* fall back to bundled */ }
        }
        return b
    }

    private fun readNew(): Map<String, Long> {
        val raw = prefs.getString("newIds", "") ?: ""
        val cutoff = System.currentTimeMillis() - NEW_DAYS * 86_400_000L
        return raw.split(',').mapNotNull {
            val p = it.split(':'); if (p.size == 2) p[1].toLongOrNull()?.let { t -> if (t > cutoff) p[0] to t else null } else null
        }.toMap()
    }

    private fun saveNew(m: Map<String, Long>) {
        prefs.edit().putString("newIds", m.entries.joinToString(",") { "${it.key}:${it.value}" }).apply()
        _newIds.value = m
    }

    fun isNew(id: String): Boolean = _newIds.value.containsKey(id)

    fun toggleFavorite(id: String) {
        val s = _favorites.value.toMutableSet()
        if (!s.add(id)) s.remove(id)
        prefs.edit().putStringSet("favorites", s).apply(); _favorites.value = s
    }

    fun markOpened(id: String) {
        val r = (listOf(id) + _recents.value.filter { it != id }).take(30)
        prefs.edit().putString("recents", r.joinToString(",")).apply(); _recents.value = r
        if (_newIds.value.containsKey(id)) saveNew(_newIds.value - id)
    }

    fun clearNew() = saveNew(emptyMap())

    fun setTheme(m: ThemeMode) { prefs.edit().putString("theme", m.name).apply(); _theme.value = m }
    fun setNotify(b: Boolean) { prefs.edit().putBoolean("notify", b).apply(); _notify.value = b }
    fun notificationsEnabled() = _notify.value

    /** Download remote catalog.json, merge (new tools get a NEW badge) and persist. Never throws. */
    suspend fun checkForUpdates(url: String = BuildConfig.CATALOG_URL): UpdateResult = lock.withLock {
        withContext(Dispatchers.IO) {
            val result = try {
                val text = download(url)
                val remote = CatalogJson.parse(text)
                if (remote.tools.isEmpty()) throw IllegalStateException("remote catalog is empty")
                val m = CatalogMerge.merge(_catalog.value, remote)
                if (!m.updated) UpdateResult.UpToDate(_catalog.value.version)
                else {
                    val tmp = File(ctx.filesDir, "catalog.json.tmp")
                    tmp.writeText(CatalogJson.toJson(m.catalog))
                    if (!tmp.renameTo(file)) { file.writeText(tmp.readText()); tmp.delete() }
                    _catalog.value = m.catalog
                    if (m.newTools.isNotEmpty()) {
                        val now = System.currentTimeMillis()
                        saveNew(_newIds.value + m.newTools.associate { it.id to now })
                    }
                    UpdateResult.Updated(m.newTools.size, m.catalog.version)
                }
            } catch (e: Exception) {
                UpdateResult.Failed(e.message ?: e.javaClass.simpleName)
            }
            val now = System.currentTimeMillis()
            val msg = when (result) {
                is UpdateResult.Updated -> if (result.newCount > 0) "${result.newCount} new tools added (catalog v${result.version})" else "Catalog updated to v${result.version}, no new tools"
                is UpdateResult.UpToDate -> "Already up to date (catalog v${result.version})"
                is UpdateResult.Failed -> "Could not check: ${result.message}"
            }
            if (result !is UpdateResult.Failed) { prefs.edit().putLong("lastChecked", now).apply(); _lastChecked.value = now }
            prefs.edit().putString("lastResult", msg).apply(); _lastResult.value = msg
            result
        }
    }

    private fun download(u: String): String {
        val c = URL(u).openConnection() as HttpURLConnection
        c.connectTimeout = 15_000; c.readTimeout = 20_000
        c.setRequestProperty("User-Agent", "MattyToolsDirectory/${BuildConfig.VERSION_NAME}")
        c.setRequestProperty("Cache-Control", "no-cache")
        try {
            if (c.responseCode != 200) throw IllegalStateException("HTTP ${c.responseCode}")
            val len = c.contentLengthLong
            if (len > 8_000_000) throw IllegalStateException("catalog too large")
            return c.inputStream.bufferedReader().use { it.readText() }
        } finally { c.disconnect() }
    }

    companion object { const val NEW_DAYS = 30 }
}
