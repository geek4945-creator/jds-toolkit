package com.geek4945.mattytools.data

import org.json.JSONArray
import org.json.JSONObject

data class Source(val title: String, val date: String, val url: String, val number: Int?)

data class Tool(
    val id: String,
    val name: String,
    val url: String,
    val host: String,
    val description: String,
    val category: String,
    val tags: List<String>,
    val sources: List<Source>,
    val video: String?,
    val addedVersion: Int,
    val added: String?,
)

/** Someone who contributed to the tool list; shown under Settings > About > Credits. `url` is optional (http/https only). */
data class Credit(val name: String, val contribution: String, val url: String? = null)

data class Category(val id: String, val name: String, val blurb: String)

data class Post(val title: String, val date: String, val url: String, val gated: Boolean, val toolsFound: Int)

data class Catalog(
    val version: Int,
    val date: String,
    val categories: List<Category>,
    val tools: List<Tool>,
    val posts: List<Post>,
    val note: String = "",
    val credits: List<Credit> = emptyList(),
) {
    fun category(id: String): Category? = categories.firstOrNull { it.id == id }
    fun countIn(categoryId: String) = tools.count { it.category == categoryId }
    val allTags: List<String> get() = tools.flatMap { it.tags }.groupingBy { it }.eachCount()
        .entries.sortedWith(compareByDescending<Map.Entry<String, Int>> { it.value }.thenBy { it.key }).map { it.key }
}

object CatalogJson {
    private fun JSONObject.str(k: String, d: String = ""): String = if (has(k) && !isNull(k)) getString(k) else d
    private fun JSONArray?.strings(): List<String> = if (this == null) emptyList() else (0 until length()).map { getString(it) }

    fun parse(text: String): Catalog {
        val o = JSONObject(text)
        val cats = o.optJSONArray("categories")?.let { a ->
            (0 until a.length()).map { i -> a.getJSONObject(i).let { Category(it.getString("id"), it.getString("name"), it.str("blurb")) } }
        } ?: emptyList()
        val tools = o.getJSONArray("items").let { a ->
            (0 until a.length()).mapNotNull { i ->
                val t = a.getJSONObject(i)
                val id = t.str("id"); val url = t.str("url")
                if (id.isEmpty() || url.isEmpty()) return@mapNotNull null
                val src = t.optJSONArray("sources")?.let { sa ->
                    (0 until sa.length()).map { j ->
                        sa.getJSONObject(j).let { Source(it.str("title"), it.str("date"), it.str("url"), if (it.has("number")) it.optInt("number") else null) }
                    }
                } ?: emptyList()
                Tool(
                    id = id, name = t.str("name", id), url = url, host = t.str("host"),
                    description = t.str("description"), category = t.str("category", "uncat"),
                    tags = t.optJSONArray("tags").strings(), sources = src,
                    video = t.str("video").ifEmpty { null },
                    addedVersion = t.optInt("addedVersion", 0), added = t.str("added").ifEmpty { null },
                )
            }
        }
        val posts = o.optJSONArray("posts")?.let { a ->
            (0 until a.length()).map { i ->
                a.getJSONObject(i).let { Post(it.str("title"), it.str("date"), it.str("url"), it.optBoolean("gated"), it.optInt("toolsFound")) }
            }
        } ?: emptyList()
        val credits = o.optJSONArray("credits")?.let { a ->
            (0 until a.length()).mapNotNull { i ->
                val c = a.optJSONObject(i) ?: return@mapNotNull null
                val name = c.str("name").trim(); val what = c.str("contribution").trim()
                if (name.isEmpty() || what.isEmpty()) return@mapNotNull null
                val link = c.str("url").trim()
                Credit(name, what, if (link.startsWith("https://") || link.startsWith("http://")) link else null)
            }
        } ?: emptyList()
        return Catalog(o.optInt("version", 0), o.str("date"), cats, tools, posts, o.str("note"), credits)
    }

    fun toJson(c: Catalog): String {
        val o = JSONObject()
        o.put("schema", 1)
        o.put("version", c.version); o.put("date", c.date); o.put("note", c.note)
        o.put("categories", JSONArray(c.categories.map { JSONObject().put("id", it.id).put("name", it.name).put("blurb", it.blurb) }))
        o.put("items", JSONArray(c.tools.map { t ->
            JSONObject().put("id", t.id).put("name", t.name).put("url", t.url).put("host", t.host)
                .put("description", t.description).put("category", t.category)
                .put("tags", JSONArray(t.tags))
                .put("sources", JSONArray(t.sources.map { s ->
                    JSONObject().put("title", s.title).put("date", s.date).put("url", s.url).also { j -> s.number?.let { j.put("number", it) } }
                }))
                .put("addedVersion", t.addedVersion)
                .also { j -> t.video?.let { j.put("video", it) }; t.added?.let { j.put("added", it) } }
        }))
        o.put("credits", JSONArray(c.credits.map { JSONObject().put("name", it.name).put("contribution", it.contribution).also { j -> it.url?.let { u -> j.put("url", u) } } }))
        o.put("posts", JSONArray(c.posts.map {
            JSONObject().put("title", it.title).put("date", it.date).put("url", it.url).put("gated", it.gated).put("toolsFound", it.toolsFound)
        }))
        return o.toString()
    }
}

/** Same normalisation as update_catalog.py: host without "www.", path without trailing slash, no utm_ params, lower case. */
fun urlKey(url: String): String {
    var u = url.trim().lowercase()
    u = u.removePrefix("https://").removePrefix("http://").substringBefore('#')
    val host = u.substringBefore('/').removePrefix("www.")
    val rest = if (u.contains('/')) "/" + u.substringAfter('/') else ""
    val path = rest.substringBefore('?').trimEnd('/')
    val query = rest.substringAfter('?', "").split('&').filter { it.isNotEmpty() && !it.startsWith("utm_") }.joinToString("&")
    return host + path + if (query.isNotEmpty()) "?$query" else ""
}

data class MergeResult(val catalog: Catalog, val newTools: List<Tool>, val updated: Boolean)

object CatalogMerge {
    /**
     * Merge a downloaded catalog into the local one. Only a strictly higher version is applied.
     * Tools are matched by id or by normalised URL; unknown ones are returned as `newTools`.
     * Local tools missing from the remote are kept (nothing is ever deleted).
     */
    fun merge(local: Catalog, remote: Catalog): MergeResult {
        if (remote.version <= local.version) return MergeResult(local, emptyList(), false)
        val byId = LinkedHashMap<String, Tool>()
        local.tools.forEach { byId[it.id] = it }
        val byUrl = HashMap<String, String>()
        local.tools.forEach { byUrl[urlKey(it.url)] = it.id }
        val added = ArrayList<Tool>()
        for (r in remote.tools) {
            val existingId = if (byId.containsKey(r.id)) r.id else byUrl[urlKey(r.url)]
            if (existingId == null) {
                byId[r.id] = r; byUrl[urlKey(r.url)] = r.id; added.add(r)
            } else {
                val old = byId.getValue(existingId)
                byId[existingId] = old.copy(
                    name = r.name.ifEmpty { old.name }, url = r.url.ifEmpty { old.url },
                    description = r.description.ifEmpty { old.description },
                    category = r.category, tags = r.tags, sources = (old.sources + r.sources).distinct(),
                    video = r.video ?: old.video,
                )
            }
        }
        val cats = LinkedHashMap<String, Category>()
        local.categories.forEach { cats[it.id] = it }
        remote.categories.forEach { cats[it.id] = it }
        val merged = Catalog(
            version = remote.version, date = remote.date, categories = cats.values.toList(),
            tools = byId.values.toList(), posts = remote.posts.ifEmpty { local.posts }, note = remote.note.ifEmpty { local.note },
            credits = remote.credits.ifEmpty { local.credits },
        )
        return MergeResult(merged, added, true)
    }
}
