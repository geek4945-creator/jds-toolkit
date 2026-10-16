/* Headless check of the category icons in the web app (docs/).
   Usage: node tests/pwa_icons_check.js   (needs playwright-core + Chrome; set PW and CHROME to override paths)
   Serves docs/ on a local port, so it tests the working tree, not the published site. Set BASE=https://... to test a live URL instead. */
const http = require('http'), fs = require('fs'), path = require('path');
const { chromium } = require(process.env.PW || '/workspace/pw/node_modules/playwright-core');
const DOCS = path.join(__dirname, '..', 'docs');
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.css': 'text/css', '.png': 'image/png', '.webmanifest': 'application/manifest+json' };
const res = []; let fails = 0;
const ok = (n, c, x) => { res.push((c ? 'PASS ' : 'FAIL ') + n + (x ? ' - ' + x : '')); if (!c) fails++; };
const OUT = process.env.OUT || '/tmp/icon-shots'; fs.mkdirSync(OUT, { recursive: true });
(async () => {
  let base = process.env.BASE, server;
  if (!base) {
    server = http.createServer((q, r) => {
      let p = decodeURIComponent(q.url.split('?')[0]); if (p.endsWith('/')) p += 'index.html';
      const f = path.join(DOCS, p); if (!f.startsWith(DOCS) || !fs.existsSync(f)) { r.writeHead(404); return r.end(); }
      r.writeHead(200, { 'content-type': TYPES[path.extname(f)] || 'application/octet-stream' }); r.end(fs.readFileSync(f));
    });
    await new Promise(r => server.listen(0, '127.0.0.1', r)); base = 'http://127.0.0.1:' + server.address().port + '/';
  }
  const browser = await chromium.launch({ executablePath: process.env.CHROME || '/usr/bin/google-chrome', args: ['--no-sandbox'] });
  const mk = async (scheme, route) => {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, colorScheme: scheme });
    const page = await ctx.newPage(); const errs = [], ext = [];
    page.on('pageerror', e => errs.push(e.message));
    page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
    page.on('request', r => { const u = new URL(r.url()); if (u.origin !== new URL(base).origin && !u.host.includes('raw.githubusercontent.com')) ext.push(r.url()); });
    if (route) await page.route('**/*', route);
    return { ctx, page, errs, ext };
  };
  const cardInfo = page => page.$$eval('.cat', els => els.map(e => { const i = e.querySelector('.cat-ico'), s = i && i.querySelector('svg'); const bb = s && s.getBBox();
    return { name: e.querySelector('.n').textContent, icon: i && i.dataset.icon, paths: s ? s.querySelectorAll('path').length : 0, w: bb ? bb.width : 0, h: bb ? bb.height : 0,
      fg: i && getComputedStyle(i).color, bg: i && getComputedStyle(i).backgroundColor }; }));

  for (const scheme of ['light', 'dark']) {
    const { ctx, page, errs, ext } = await mk(scheme);
    await page.goto(base); await page.waitForSelector('.cat .cat-ico svg path');
    const info = await cardInfo(page);
    ok(`[${scheme}] 13 category cards all have an inline SVG icon`, info.length === 13 && info.every(i => i.icon && i.paths > 0 && i.w > 6 && i.h > 6), info.length + ' cards');
    ok(`[${scheme}] every card has a different icon`, new Set(info.map(i => i.icon)).size === info.length, info.map(i => i.icon).join(','));
    ok(`[${scheme}] icon colour differs from tile colour`, info.every(i => i.fg !== i.bg), info[0].fg + ' on ' + info[0].bg);
    ok(`[${scheme}] no horizontal overflow`, await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({ path: `${OUT}/home-${scheme}.png`, fullPage: true });
    await page.click('.cat >> nth=0'); await page.waitForSelector('.cat-head .cat-ico svg');
    ok(`[${scheme}] category screen shows the small badge`, await page.isVisible('.cat-head .cat-ico.sm'));
    await page.screenshot({ path: `${OUT}/category-${scheme}.png` });
    ok(`[${scheme}] no console errors / no external requests`, errs.length === 0 && ext.length === 0, errs.concat(ext).join(' | '));
    await ctx.close();
  }

  // new category without an icon -> default folder icon; declared icon name wins; unknown declared name -> default
  const catalogRoute = async route => {
    const u = route.request().url();
    if (!u.endsWith('/catalog.json')) return route.continue();
    const j = JSON.parse(fs.readFileSync(path.join(DOCS, 'catalog.json'), 'utf8'));
    j.categories.push({ id: 'zz1', name: 'Zed One', blurb: 'x' }, { id: 'zz2', name: 'Zed Two', blurb: 'x', icon: 'palette' }, { id: 'zz3', name: 'Zed Three', blurb: 'x', icon: 'nope' });
    ['zz1', 'zz2', 'zz3'].forEach(c => j.items.push({ id: c + '-t', name: c, url: 'https://example.com/' + c, host: 'example.com', description: 'd', category: c, tags: [], sources: [] }));
    route.fulfill({ contentType: 'application/json', body: JSON.stringify(j) });
  };
  let t = await mk('light', catalogRoute);
  await t.page.goto(base); await t.page.waitForSelector('.cat .cat-ico svg');
  const m = Object.fromEntries((await cardInfo(t.page)).map(i => [i.name, i.icon]));
  ok('future category with no icon gets the default folder icon', m['Zed One'] === 'folder', m['Zed One']);
  ok('future category can name an icon', m['Zed Two'] === 'palette', m['Zed Two']);
  ok('unknown icon name falls back to default', m['Zed Three'] === 'folder', m['Zed Three']);
  await t.ctx.close();

  // icons.json unavailable -> app still works, just without icons
  t = await mk('light', route => route.request().url().endsWith('/icons.json') ? route.fulfill({ status: 404, body: '' }) : route.continue());
  await t.page.goto(base); await t.page.waitForSelector('.cat');
  ok('without icons.json the cards still render (no icon, no crash)', (await t.page.$$('.cat')).length === 13 && (await t.page.$$('.cat-ico')).length === 0 && !t.errs.some(e => e.startsWith('Uncaught') || e.includes('TypeError')));
  await t.ctx.close();

  // service worker precaches icons.json
  t = await mk('light'); await t.page.goto(base); await t.page.waitForSelector('.cat');
  await t.page.waitForFunction(() => navigator.serviceWorker && navigator.serviceWorker.controller || true);
  const cached = await t.page.evaluate(async () => { await navigator.serviceWorker.ready; const ks = await caches.keys(); const c = await caches.open(ks[0]); return !!(await c.match('icons.json')); });
  ok('service worker has icons.json cached for offline', cached);
  await t.ctx.close();

  await browser.close(); if (server) server.close();
  console.log(res.join('\n')); console.log(fails ? `${fails} FAILED` : 'ALL PASSED'); process.exit(fails ? 1 : 0);
})();
