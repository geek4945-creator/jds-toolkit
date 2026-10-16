package com.geek4945.mattytools.data

import org.json.JSONObject

/**
 * Category icon artwork + mapping, parsed from assets/icons.json (same file the web app uses, so both stay in sync).
 * Artwork is a list of SVG path strings per icon name on a 24x24 grid (Material Icons, Apache License 2.0).
 * Resolution: the category's own `icon` (from catalog.json) if known, else the id map in icons.json, else the default icon.
 */
class CategoryIconSet(
    val icons: Map<String, List<String>>,
    private val byCategory: Map<String, String>,
    private val default: String,
) {
    fun nameFor(categoryId: String, declared: String = ""): String {
        if (declared.isNotEmpty() && declared in icons) return declared
        val mapped = byCategory[categoryId]
        if (mapped != null && mapped in icons) return mapped
        return default
    }

    fun pathsFor(categoryId: String, declared: String = ""): List<String> = icons[nameFor(categoryId, declared)].orEmpty()

    companion object {
        val EMPTY = CategoryIconSet(emptyMap(), emptyMap(), "")

        fun parse(text: String): CategoryIconSet {
            val o = JSONObject(text)
            val ic = o.getJSONObject("icons")
            val icons = HashMap<String, List<String>>()
            for (k in ic.keys()) {
                val a = ic.getJSONArray(k)
                icons[k] = (0 until a.length()).map { a.getString(it) }
            }
            val cm = o.optJSONObject("categories")
            val cats = HashMap<String, String>()
            if (cm != null) for (k in cm.keys()) cats[k] = cm.getString(k)
            return CategoryIconSet(icons, cats, o.optString("default", "folder"))
        }
    }
}
