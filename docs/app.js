/* JD's Toolkit (unofficial) - iPhone-friendly PWA. Plain JS, no backend, no analytics.
   Mirrors the Android app: categories, search, tag filters, favorites, recents, share, NEW badges,
   About, Settings and a ~30 day catalog refresh from the public catalog.json on GitHub. */
(function () {
  'use strict';

  var APP_VERSION = '1.0.2-web';
  var REMOTE_URL = 'https://raw.githubusercontent.com/geek4945-creator/matty-tools-directory/main/catalog.json';
  var REPO_URL = 'https://github.com/geek4945-creator/matty-tools-directory';
  var CHECK_EVERY_MS = 30 * 86400000;
  var NEW_DAYS = 30;
  var P = 'jdt:';

  /* ---------- storage (never throws; falls back to memory if blocked) ---------- */
  var mem = {};
  function sget(k, def) {
    try { var v = localStorage.getItem(P + k); return v === null ? def : JSON.parse(v); } catch (e) { return k in mem ? mem[k] : def; }
  }
  function sset(k, v) {
    mem[k] = v;
    try { localStorage.setItem(P + k, JSON.stringify(v)); } catch (e) { /* storage full or blocked */ }
  }

  /* ---------- state ---------- */
  var catalog = null;            // {version,date,categories,tools,posts,note}
  var byId = {};
  var favs = sget('favs', []);
  var recents = sget('recents', []);
  var newIds = pruneNew(sget('newIds', {}));
  var themeMode = sget('theme', 'system');
  var searchState = { q: '', tags: [] };
  var catTags = {};              // category id -> selected tags
  var checking = false;

  /* ---------- helpers ---------- */
  function $(id) { return document.getElementById(id); }
  function h(tag, attrs, kids) {
    var e = document.createElement(tag);
    if (attrs) for (var k in attrs) {
      var v = attrs[k];
      if (v === false || v == null) continue;
      if (k === 'class') e.className = v;
      else if (k === 'text') e.textContent = v;
      else if (k.slice(0, 2) === 'on') e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v === true ? '' : v);
    }
    (kids || []).forEach(function (c) { if (c != null && c !== false) e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return e;
  }
  function safeUrl(u) { try { var x = new URL(u); return (x.protocol === 'http:' || x.protocol === 'https:') ? x.href : null; } catch (e) { return null; } }
  function tagLabel(t) { t = String(t).replace(/-/g, ' '); return t.charAt(0).toUpperCase() + t.slice(1); }
  function plural(n, s) { return n + ' ' + s + (n === 1 ? '' : 's'); }
  function pruneNew(m) {
    var cutoff = Date.now() - NEW_DAYS * 86400000, o = {};
    for (var k in (m || {})) if (m[k] > cutoff) o[k] = m[k];
    return o;
  }
  function fmtDate(ms) {
    if (!ms) return 'Never';
    try { return new Date(ms).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }); } catch (e) { return new Date(ms).toISOString(); }
  }
  var toastTimer;
  function toast(msg) {
    var t = $('toast'); t.textContent = msg; t.hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { t.hidden = true; }, 2600);
  }

  /* ---------- catalog ---------- */
  function normalize(raw) {
    if (!raw || typeof raw !== 'object' || !Array.isArray(raw.items) || typeof raw.version !== 'number') return null;
    var tools = [];
    raw.items.forEach(function (t) {
      if (!t || !t.id || !t.name || !safeUrl(t.url)) return;
      tools.push({
        id: String(t.id), name: String(t.name), url: safeUrl(t.url),
        host: String(t.host || (function () { try { return new URL(t.url).hostname.replace(/^www\./, ''); } catch (e) { return ''; } })()),
        description: String(t.description || ''), category: String(t.category || 'uncat'),
        tags: Array.isArray(t.tags) ? t.tags.map(String) : [],
        sources: Array.isArray(t.sources) ? t.sources.filter(function (s) { return s && safeUrl(s.url); }).map(function (s) { return { title: String(s.title || ''), url: safeUrl(s.url) }; }) : [],
        video: t.video ? safeUrl(t.video) : null
      });
    });
    var cats = (Array.isArray(raw.categories) ? raw.categories : []).filter(function (c) { return c && c.id && c.name; })
      .map(function (c) { return { id: String(c.id), name: String(c.name), blurb: String(c.blurb || '') }; });
    var credits = (Array.isArray(raw.credits) ? raw.credits : []).filter(function (c) { return c && String(c.name || '').trim() && String(c.contribution || '').trim(); })
      .map(function (c) { return { name: String(c.name).trim(), contribution: String(c.contribution).trim(), url: c.url ? safeUrl(c.url) : null }; });
    return {
      version: raw.version, date: String(raw.date || ''), categories: cats, tools: tools,
      posts: Array.isArray(raw.posts) ? raw.posts : [], note: String(raw.note || ''), credits: credits
    };
  }
  function urlKey(u) {
    try { var x = new URL(u); return (x.host.replace(/^www\./, '') + x.pathname.replace(/\/+$/, '')).toLowerCase(); } catch (e) { return u; }
  }
  /* Same rules as the Android app: only a strictly higher version is applied, tools are matched by id or
     normalised URL, unknown ones are "new", and nothing is ever deleted locally. */
  function merge(local, remote) {
    if (remote.version <= local.version) return { catalog: local, added: [], updated: false };
    var map = {}, order = [], urls = {}, added = [];
    local.tools.forEach(function (t) { map[t.id] = t; order.push(t.id); urls[urlKey(t.url)] = t.id; });
    remote.tools.forEach(function (r) {
      var ex = map[r.id] ? r.id : urls[urlKey(r.url)];
      if (!ex) { map[r.id] = r; order.push(r.id); urls[urlKey(r.url)] = r.id; added.push(r); }
      else {
        var o = map[ex];
        map[ex] = { id: o.id, name: r.name || o.name, url: r.url || o.url, host: r.host || o.host, description: r.description || o.description,
          category: r.category, tags: r.tags, sources: o.sources.concat(r.sources.filter(function (s) { return !o.sources.some(function (x) { return x.url === s.url; }); })), video: r.video || o.video };
      }
    });
    var cats = {}, corder = [];
    local.categories.concat(remote.categories).forEach(function (c) { if (!cats[c.id]) corder.push(c.id); cats[c.id] = c; });
    return {
      catalog: { version: remote.version, date: remote.date, categories: corder.map(function (i) { return cats[i]; }),
        tools: order.map(function (i) { return map[i]; }), posts: remote.posts.length ? remote.posts : local.posts, note: remote.note || local.note,
        credits: remote.credits.length ? remote.credits : local.credits },
      added: added, updated: true
    };
  }
  function setCatalog(c) {
    catalog = c; byId = {};
    c.tools.forEach(function (t) { byId[t.id] = t; });
  }
  function category(id) { return catalog.categories.filter(function (c) { return c.id === id; })[0]; }
  function toolsIn(cid) { return catalog.tools.filter(function (t) { return t.category === cid; }).sort(byName); }
  function byName(a, b) { return a.name.toLowerCase() < b.name.toLowerCase() ? -1 : a.name.toLowerCase() > b.name.toLowerCase() ? 1 : 0; }
  function topTags(tools, n) {
    var cnt = {};
    tools.forEach(function (t) { t.tags.forEach(function (g) { cnt[g] = (cnt[g] || 0) + 1; }); });
    return Object.keys(cnt).sort(function (a, b) { return cnt[b] - cnt[a] || (a < b ? -1 : 1); }).slice(0, n);
  }

  function loadCatalog() {
    return fetch('catalog.json', { cache: 'no-cache' }).then(function (r) {
      if (!r.ok) throw new Error('bundled catalog HTTP ' + r.status);
      return r.json();
    }).then(function (raw) {
      var bundled = normalize(raw);
      if (!bundled) throw new Error('bad bundled catalog');
      var stored = normalize(sget('catalog', null));
      var cur = stored || bundled;
      if (stored && bundled.version > stored.version) {   // a newer app build shipped a newer snapshot
        var m = merge(stored, bundled);
        cur = m.catalog; markNew(m.added); sset('catalog', rawOf(cur));
      }
      if (!cur.credits.length) cur.credits = bundled.credits;   // catalogs saved by older versions have no credits
      setCatalog(cur);
    }).catch(function (err) {
      var stored = normalize(sget('catalog', null));   // offline and not cached by the service worker yet
      if (!stored) throw err;
      setCatalog(stored);
    });
  }
  function rawOf(c) {
    return { version: c.version, date: c.date, note: c.note, categories: c.categories, posts: c.posts, credits: c.credits,
      items: c.tools.map(function (t) { return { id: t.id, name: t.name, url: t.url, host: t.host, description: t.description, category: t.category, tags: t.tags, sources: t.sources, video: t.video }; }) };
  }
  function markNew(added) {
    if (!added.length) return;
    var now = Date.now();
    added.forEach(function (t) { newIds[t.id] = now; });
    sset('newIds', newIds);
  }

  /* ---------- update check ---------- */
  var banner = { dismissed: false };
  function checkForUpdates(manual) {
    if (checking) return Promise.resolve(null);
    checking = true; render();
    var ctl = typeof AbortController === 'function' ? new AbortController() : null;
    var to = setTimeout(function () { if (ctl) ctl.abort(); }, 15000);
    var go = (typeof navigator !== 'undefined' && navigator.onLine === false) ? Promise.reject(new Error('offline')) :
      fetch(REMOTE_URL, { cache: 'no-cache', signal: ctl ? ctl.signal : undefined });
    return go.then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    }).then(function (raw) {
      var remote = normalize(raw);
      if (!remote) throw new Error('the downloaded file was not a valid catalog');
      var m = merge(catalog, remote);
      sset('lastChecked', Date.now());
      var res;
      if (m.updated) {
        setCatalog(m.catalog); sset('catalog', rawOf(m.catalog)); markNew(m.added);
        res = { status: 'updated', newCount: m.added.length, version: m.catalog.version };
        sset('lastResult', m.added.length ? plural(m.added.length, 'new tool') + ' added (catalog v' + m.catalog.version + ')' : 'Catalog updated to v' + m.catalog.version + ', no new tools');
      } else {
        res = { status: 'current', newCount: 0, version: catalog.version };
        sset('lastResult', 'Already up to date (catalog v' + catalog.version + ')');
      }
      return res;
    }).catch(function (e) {
      var offline = typeof navigator !== 'undefined' && navigator.onLine === false;
      sset('lastResult', offline ? 'No connection. Your saved catalog still works. Try again when online.' : 'Could not check for updates (' + (e && e.name === 'AbortError' ? 'timed out' : (e && e.message) || 'unknown error') + ')');
      return { status: 'error' };
    }).then(function (res) {
      clearTimeout(to); checking = false;
      banner.dismissed = false;
      banner.newCount = res.status === 'updated' ? res.newCount : 0;
      render();
      if (manual) toast(sget('lastResult', ''));
      return res;
    });
  }
  function maybeAutoCheck() {
    var last = sget('lastChecked', 0);
    if (!last || Date.now() - last > CHECK_EVERY_MS) checkForUpdates(false);
  }

  /* ---------- user data ---------- */
  function isFav(id) { return favs.indexOf(id) >= 0; }
  function toggleFav(id) {
    favs = isFav(id) ? favs.filter(function (x) { return x !== id; }) : [id].concat(favs);
    sset('favs', favs); render(true);
  }
  function opened(id) {
    recents = [id].concat(recents.filter(function (x) { return x !== id; })).slice(0, 30); sset('recents', recents);
    if (newIds[id]) { delete newIds[id]; sset('newIds', newIds); }
  }
  function shareTool(t) {
    var text = t.name + (t.description ? ' - ' + t.description.slice(0, 140) : '') + '\n' + t.url +
      '\n(shared from JD\'s Toolkit)';
    var done = function () { toast('Link copied'); };
    if (navigator.share) {
      navigator.share({ title: t.name, text: text, url: t.url }).catch(function (e) { if (e && e.name !== 'AbortError') copyText(t.url + '', done); });
    } else copyText(text, done);
  }
  function copyText(text, ok) {
    function fallback() {
      var ta = h('textarea', { 'aria-hidden': 'true', style: 'position:fixed;top:0;left:0;opacity:0' }); ta.value = text;
      document.body.appendChild(ta); ta.focus(); ta.select(); ta.setSelectionRange(0, text.length);
      var good = false; try { good = document.execCommand('copy'); } catch (e) { /* ignore */ }
      document.body.removeChild(ta);
      if (good) ok(); else window.prompt('Copy this link:', text);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(ok, fallback); else fallback();
  }

  /* ---------- theme ---------- */
  var mq = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  function applyTheme() {
    var dark = themeMode === 'dark' || (themeMode === 'system' && mq && mq.matches);
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
    var m = document.querySelector('meta[name=theme-color]');
    if (m) m.setAttribute('content', dark ? '#0F1115' : '#FBFBFE');
  }
  if (mq) (mq.addEventListener ? mq.addEventListener('change', applyTheme) : mq.addListener && mq.addListener(applyTheme));
  applyTheme();

  /* ---------- components ---------- */
  function toolCard(t) {
    var src = t.sources.filter(function (s) { return s.url.indexOf('docs.google.com') < 0; })[0];
    var kids = [
      h('a', { class: 'open', href: t.url, target: '_blank', rel: 'noopener noreferrer', onclick: function () { opened(t.id); } }, [
        h('div', { class: 'nm' }, [h('span', { text: t.name }), newIds[t.id] ? h('span', { class: 'new', text: 'NEW' }) : null]),
        t.description ? h('div', { class: 'ds', text: t.description }) : null,
        h('div', { class: 'ho', text: t.host })
      ]),
      t.tags.length ? h('div', { class: 'tg' }, t.tags.slice(0, 3).map(function (g) { return h('span', { class: 'lbl', text: tagLabel(g) }); })) : null,
      src ? h('a', { class: 'src', href: src.url, target: '_blank', rel: 'noopener noreferrer', text: 'From: ' + (src.title || 'newsletter post') }) : null
    ];
    return h('div', { class: 'card', 'data-id': t.id }, [
      h('div', { class: 'body' }, kids),
      h('div', { class: 'acts' }, [
        h('button', { class: 'act' + (isFav(t.id) ? ' on' : ''), type: 'button', 'aria-pressed': isFav(t.id) ? 'true' : 'false', 'aria-label': (isFav(t.id) ? 'Remove from saved: ' : 'Save: ') + t.name,
          'data-act': 'fav', text: isFav(t.id) ? '\u2605' : '\u2606', onclick: function () { toggleFav(t.id); } }),
        h('button', { class: 'act', type: 'button', 'aria-label': 'Share ' + t.name, 'data-act': 'share', text: '\u2197', onclick: function () { shareTool(t); } })
      ])
    ]);
  }
  function tagChips(tags, selected, onToggle) {
    if (!tags.length) return null;
    return h('div', { class: 'chips', role: 'group', 'aria-label': 'Filter by use' }, tags.map(function (g) {
      var on = selected.indexOf(g) >= 0;
      return h('button', { class: 'chip', type: 'button', 'aria-pressed': on ? 'true' : 'false', 'data-tag': g, text: tagLabel(g), onclick: function () { onToggle(g); } });
    }));
  }
  function toggleIn(arr, v) { return arr.indexOf(v) >= 0 ? arr.filter(function (x) { return x !== v; }) : arr.concat(v); }
  function listOf(tools, emptyMsg) {
    if (!tools.length) return h('div', { class: 'empty', text: emptyMsg });
    return h('div', { class: 'list' }, tools.map(toolCard));
  }
  function sec(title, link) {
    return h('h2', { class: 'sec' }, [h('span', { text: title }), link ? h('a', { href: link[1], text: link[0] }) : null]);
  }

  /* ---------- screens ---------- */
  function screenHome() {
    var v = h('div');
    var cats = catalog.categories.map(function (c) { return { c: c, n: toolsIn(c.id).length }; }).filter(function (x) { return x.n > 0; });
    var newTools = catalog.tools.filter(function (t) { return newIds[t.id]; });
    v.appendChild(h('p', { class: 'muted', id: 'subtitle', text: "Handy tools and sites, sorted by what they're for." }));
    v.appendChild(h('p', { class: 'muted', text: plural(catalog.tools.length, 'tool') + ' in ' + plural(cats.length, 'category').replace('categorys', 'categories') + ' \u00B7 catalog v' + catalog.version }));
    if (newTools.length) {
      v.appendChild(sec('New', ['See all ' + newTools.length, '#/new']));
      v.appendChild(h('div', { class: 'hrow' }, newTools.slice(0, 8).map(toolCard)));
    }
    var rec = recents.map(function (id) { return byId[id]; }).filter(Boolean).slice(0, 8);
    if (rec.length) {
      v.appendChild(sec('Recently opened', recents.length > 8 ? ['See all', '#/recent'] : null));
      v.appendChild(h('div', { class: 'hrow' }, rec.map(toolCard)));
    }
    v.appendChild(sec('Categories'));
    v.appendChild(h('div', { class: 'grid' }, cats.map(function (x) {
      return h('a', { class: 'cat', href: '#/c/' + encodeURIComponent(x.c.id) }, [
        h('div', { class: 'n', text: x.c.name }), h('div', { class: 'b', text: x.c.blurb }), h('div', { class: 'c', text: plural(x.n, 'tool') })
      ]);
    })));
    return { title: "JD's Toolkit", node: v };
  }
  function screenCategory(cid) {
    var c = category(cid);
    if (!c) return { title: 'Not found', node: h('div', { class: 'empty', text: 'That category does not exist.' }), back: true };
    var all = toolsIn(cid), sel = catTags[cid] || [];
    var shown = all.filter(function (t) { return sel.every(function (g) { return t.tags.indexOf(g) >= 0; }); });
    var v = h('div');
    if (c.blurb) v.appendChild(h('p', { class: 'muted', text: c.blurb }));
    v.appendChild(tagChips(topTags(all, 24), sel, function (g) { catTags[cid] = toggleIn(sel, g); render(true); }));
    v.appendChild(h('p', { class: 'muted', text: plural(shown.length, 'tool') }));
    v.appendChild(listOf(shown, 'No tools match these filters.'));
    return { title: c.name, node: v, back: true };
  }
  function screenSearch() {
    var v = h('div');
    var input = h('input', { class: 'search', type: 'search', id: 'q', placeholder: 'Search name, use, site\u2026', autocomplete: 'off', autocapitalize: 'none', autocorrect: 'off', spellcheck: 'false', enterkeyhint: 'search', 'aria-label': 'Search all tools', value: searchState.q });
    var chipsBox = h('div'), count = h('p', { class: 'muted' }), results = h('div');
    function run() {
      var words = searchState.q.trim().toLowerCase().split(/\s+/).filter(Boolean);
      var found = catalog.tools.filter(function (t) {
        if (!searchState.tags.every(function (g) { return t.tags.indexOf(g) >= 0; })) return false;
        var cat = category(t.category), cn = cat ? cat.name.toLowerCase() : '';
        return words.every(function (w) {
          return t.name.toLowerCase().indexOf(w) >= 0 || t.description.toLowerCase().indexOf(w) >= 0 || t.host.toLowerCase().indexOf(w) >= 0 ||
            t.tags.some(function (g) { return g.replace(/-/g, ' ').indexOf(w) >= 0; }) || cn.indexOf(w) >= 0;
        });
      }).sort(byName);
      chipsBox.innerHTML = '';
      var c = tagChips(topTags(catalog.tools, 24), searchState.tags, function (g) { searchState.tags = toggleIn(searchState.tags, g); run(); });
      if (c) chipsBox.appendChild(c);
      count.textContent = plural(found.length, 'result');
      results.innerHTML = ''; results.appendChild(listOf(found, 'No tools match. Try fewer words or clear a filter.'));
    }
    input.addEventListener('input', function () { searchState.q = input.value; run(); });
    v.appendChild(input); v.appendChild(chipsBox); v.appendChild(count); v.appendChild(results);
    run();
    return { title: 'Search', node: v, tab: 'search' };
  }
  function screenFavorites() {
    var v = h('div');
    var f = favs.map(function (id) { return byId[id]; }).filter(Boolean);
    v.appendChild(listOf(f, 'Nothing saved yet. Tap the star on any tool to keep it here.'));
    var rec = recents.map(function (id) { return byId[id]; }).filter(Boolean);
    v.appendChild(sec('Recently opened'));
    v.appendChild(listOf(rec, 'Tools you open will show up here.'));
    if (rec.length) v.appendChild(h('button', { class: 'btn block', type: 'button', style: 'margin-top:12px', text: 'Clear recently opened', onclick: function () { recents = []; sset('recents', recents); render(true); } }));
    return { title: 'Saved', node: v, tab: 'favorites' };
  }
  function screenRecent() {
    var rec = recents.map(function (id) { return byId[id]; }).filter(Boolean);
    return { title: 'Recently opened', node: listOf(rec, 'Tools you open will show up here.'), back: true };
  }
  function screenNew() {
    var n = catalog.tools.filter(function (t) { return newIds[t.id]; }).sort(byName);
    var v = h('div');
    v.appendChild(listOf(n, 'No new tools right now. Use Settings \u2192 Check for updates now.'));
    if (n.length) v.appendChild(h('button', { class: 'btn block', type: 'button', style: 'margin-top:12px', text: 'Clear NEW badges', onclick: function () { newIds = {}; sset('newIds', newIds); render(true); } }));
    return { title: 'New tools', node: v, back: true };
  }
  function screenSettings() {
    var v = h('div');
    var seg = h('div', { class: 'seg', role: 'group', 'aria-label': 'Theme' }, [['system', 'System'], ['light', 'Light'], ['dark', 'Dark']].map(function (o) {
      return h('button', { type: 'button', 'data-theme-opt': o[0], 'aria-pressed': themeMode === o[0] ? 'true' : 'false', text: o[1], onclick: function () { themeMode = o[0]; sset('theme', themeMode); applyTheme(); render(true); } });
    }));
    v.appendChild(h('div', { class: 'panel' }, [h('h3', { text: 'Theme' }), seg]));
    var last = sget('lastChecked', 0), res = sget('lastResult', '');
    v.appendChild(h('div', { class: 'panel' }, [
      h('h3', { text: 'Catalog updates' }),
      h('p', { text: 'Catalog v' + catalog.version + ' (' + catalog.date + '): ' + plural(catalog.tools.length, 'tool') }),
      h('p', { id: 'lastChecked', text: 'Last checked: ' + fmtDate(last) }),
      res ? h('p', { id: 'lastResult', class: 'muted', text: res }) : null,
      h('button', { class: 'btn primary block', id: 'checkNow', type: 'button', disabled: checking, text: checking ? 'Checking\u2026' : 'Check for updates now', onclick: function () { checkForUpdates(true); } }),
      h('p', { class: 'muted', text: 'This web app checks for new tools when you open it, at most about once a month, or whenever you tap the button. ' +
        'On iPhone a web app cannot run in the background or send reliable notifications, so you will see a "N new tools added" banner here instead.' })
    ]));
    v.appendChild(h('div', { class: 'panel' }, [
      h('h3', { text: 'Your data' }),
      h('p', { class: 'muted', text: plural(favs.length, 'saved tool') + ', ' + plural(recents.length, 'recent tool') + '. Stored only on this device, in this browser or Home Screen app. Nothing is uploaded.' })
    ]));
    v.appendChild(h('a', { class: 'btn block', href: '#/about', text: "About JD's Toolkit" }));
    return { title: 'Settings', node: v, tab: 'settings' };
  }
  function screenAbout() {
    var v = h('div');
    v.appendChild(h('div', { class: 'panel warn' }, [h('h3', { text: 'Unofficial, fan-made toolkit' }),
      h('p', { text: "JD's Toolkit is an independent, fan-made index. It is NOT made by, affiliated with, or endorsed by the people or sites credited below or the tools it links to." })]));
    v.appendChild(h('h2', { class: 'sec' }, [h('span', { text: 'Credits' })]));
    v.appendChild(h('div', { id: 'credits' }, catalog.credits.map(function (c) {
      return h('div', { class: 'panel credit' }, [h('h3', { text: c.name }), h('p', { text: c.contribution }),
        c.url ? h('a', { class: 'btn block', href: c.url, target: '_blank', rel: 'noopener noreferrer', text: 'Open ' + c.url.replace(/^https?:\/\/(www\.)?/, '').replace(/\/.*$/, '') }) : null]);
    })));
    v.appendChild(h('p', { class: 'muted', text: 'Each tool also shows where it came from on its "From:" line. Thank you to everyone who shares good finds.' }));
    v.appendChild(h('div', { class: 'panel' }, [h('h3', { text: 'What is in the list' }),
      h('p', { text: 'Catalog v' + catalog.version + ' (' + catalog.date + '): ' + plural(catalog.tools.length, 'tool') + '. Only openly readable parts of sources are listed (nothing behind a sign-up or paywall). Categories and tags are assigned automatically from keywords, so a few may be off.' })]));
    v.appendChild(h('div', { class: 'panel' }, [h('h3', { text: 'Privacy' }),
      h('p', { text: 'No account, no ads, no analytics. Favorites and history stay on your device. The only request this app makes itself is downloading the public catalog file from GitHub.' })]));
    v.appendChild(h('a', { class: 'btn block', href: REPO_URL, target: '_blank', rel: 'noopener noreferrer', text: 'Project page on GitHub' }));
    v.appendChild(h('p', { class: 'muted', text: 'Version ' + APP_VERSION }));
    return { title: 'About', node: v, back: true, tab: 'settings' };
  }

  /* ---------- router ---------- */
  var lastScreenKey = '';
  function route() {
    var hash = location.hash.replace(/^#/, '') || '/';
    var parts = hash.split('/').filter(Boolean);
    switch (parts[0]) {
      case undefined: return Object.assign({ tab: 'home' }, screenHome());
      case 'c': return Object.assign({ tab: 'home' }, screenCategory(decodeURIComponent(parts[1] || '')));
      case 'search': return screenSearch();
      case 'favorites': return screenFavorites();
      case 'recent': return Object.assign({ tab: 'favorites' }, screenRecent());
      case 'new': return Object.assign({ tab: 'home' }, screenNew());
      case 'settings': return screenSettings();
      case 'about': return screenAbout();
      default: return Object.assign({ tab: 'home' }, screenHome());
    }
  }
  function render(keepScroll) {
    if (!catalog) return;
    var focusId = document.activeElement && document.activeElement.id;
    var y = window.scrollY, s;
    try { s = route(); } catch (e) { console.error(e); s = { title: 'Error', node: h('div', { class: 'empty', text: 'Something went wrong. Reload the app.' }) }; }
    var view = $('view');
    view.innerHTML = ''; view.appendChild(s.node);
    $('title').textContent = s.title;
    document.title = s.title === "JD's Toolkit" ? s.title : s.title + " - JD's Toolkit";
    $('back').hidden = !s.back;
    Array.prototype.forEach.call(document.querySelectorAll('#tabbar a'), function (a) {
      if (a.getAttribute('data-tab') === s.tab) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
    renderBanner();
    var key = location.hash;
    if (keepScroll === true && key === lastScreenKey) window.scrollTo(0, y); else if (key !== lastScreenKey) window.scrollTo(0, 0);
    lastScreenKey = key;
    if (focusId === 'q' && $('q')) { var q = $('q'); q.focus(); try { q.setSelectionRange(q.value.length, q.value.length); } catch (e) { /* ignore */ } }
  }
  function renderBanner() {
    var b = $('banner');
    if (!banner.newCount || banner.dismissed) { b.hidden = true; b.innerHTML = ''; return; }
    b.hidden = false; b.innerHTML = '';
    b.appendChild(h('span', { class: 'msg', text: plural(banner.newCount, 'new tool') + ' added' }));
    b.appendChild(h('a', { class: 'btn primary', href: '#/new', text: 'View', onclick: function () { banner.dismissed = true; } }));
    b.appendChild(h('button', { class: 'btn', type: 'button', text: 'Dismiss', onclick: function () { banner.dismissed = true; renderBanner(); } }));
  }

  $('back').addEventListener('click', function () {
    if (history.length > 1 && document.referrer !== undefined && window.__navCount > 0) history.back(); else location.hash = '#/';
  });
  window.__navCount = 0;
  window.addEventListener('hashchange', function () { window.__navCount++; render(); });

  /* ---------- start ---------- */
  function start() {
    loadCatalog().then(function () { render(); maybeAutoCheck(); }).catch(function (e) {
      console.error(e);
      $('view').appendChild(h('div', { class: 'empty' }, [h('p', { text: 'Could not load the tool catalog. Check your connection and reload.' }),
        h('button', { class: 'btn primary', type: 'button', text: 'Reload', onclick: function () { location.reload(); } })]));
    });
  }
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () { navigator.serviceWorker.register('sw.js').catch(function (e) { console.warn('Service worker not registered: ' + e.message); }); });
  }
  start();
})();
