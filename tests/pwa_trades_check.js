/* Headless check of the Politician Trades digest in the web app (docs/). Usage: node tests/pwa_trades_check.js
   Serves docs/ locally (or set BASE=https://... for a live URL). Needs playwright-core + Chrome (PW / CHROME env vars override paths). */
const http = require('http'), fs = require('fs'), path = require('path');
const { chromium } = require(process.env.PW || '/workspace/pw/node_modules/playwright-core');
const DOCS = path.join(__dirname, '..', 'docs');
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.css': 'text/css', '.png': 'image/png', '.webmanifest': 'application/manifest+json' };
const res = []; let fails = 0; const ok = (n, c, x) => { res.push((c ? 'PASS ' : 'FAIL ') + n + (x ? ' - ' + x : '')); if (!c) fails++; };
const OUT = process.env.OUT || '/tmp/trade-shots'; fs.mkdirSync(OUT, { recursive: true });
(async () => {
  let base = process.env.BASE, server;
  if (!base) {
    server = http.createServer((q, r) => { let p = decodeURIComponent(q.url.split('?')[0]); if (p.endsWith('/')) p += 'index.html';
      const f = path.join(DOCS, p); if (!f.startsWith(DOCS) || !fs.existsSync(f)) { r.writeHead(404); return r.end(); }
      r.writeHead(200, { 'content-type': TYPES[path.extname(f)] || 'application/octet-stream' }); r.end(fs.readFileSync(f)); });
    await new Promise(r => server.listen(0, '127.0.0.1', r)); base = 'http://127.0.0.1:' + server.address().port + '/';
  }
  const data = JSON.parse(fs.readFileSync(path.join(DOCS, 'trades.json'), 'utf8'));
  const browser = await chromium.launch({ executablePath: process.env.CHROME || '/usr/bin/google-chrome', args: ['--no-sandbox'] });
  const mk = async (scheme, route) => { const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, colorScheme: scheme });
    const page = await ctx.newPage(); const errs = [], ext = [];
    page.on('pageerror', e => errs.push(e.message)); page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
    page.on('request', r => { const u = new URL(r.url()); if (u.origin !== new URL(base).origin && !u.host.includes('raw.githubusercontent.com')) ext.push(r.url()); });
    if (route) await page.route('**/*', route); return { ctx, page, errs, ext }; };

  for (const scheme of ['light', 'dark']) {
    const { ctx, page, errs, ext } = await mk(scheme);
    await page.goto(base + '#/c/money'); await page.waitForSelector('#trades-card');
    ok(`[${scheme}] Politician Trades card is at the top of Money, Jobs & Business`, await page.evaluate(() => { const v = document.querySelector('main'); const c = document.getElementById('trades-card'); const first = v.querySelector('.feature, .card, .chips'); return first === c; }));
    await page.click('#trades-card'); await page.waitForSelector('#trade-list .card');
    ok(`[${scheme}] digest opens, title and back button`, (await page.textContent('#title')) === 'Politician Trades' && await page.isVisible('#back'));
    ok(`[${scheme}] shows 45-day delay and not-advice wording`, (await page.textContent('#trades-delay')).includes('45 days') && (await page.textContent('#trades')).includes('not investment advice'));
    ok(`[${scheme}] last-updated stamp`, /refreshed .*latest filing \d{4}-\d\d-\d\d/.test(await page.textContent('#trades-stamp')), await page.textContent('#trades-stamp'));
    const n0 = await page.$$eval('#trade-list .card', e => e.length);
    ok(`[${scheme}] list renders (max 300)`, n0 > 0 && n0 <= 300, n0);
    const f = await page.$eval('#trade-list .card', e => ({ name: e.querySelector('.tr-name').textContent, hasAmt: !!e.querySelector('.tr-amt').textContent, side: e.querySelector('.tr-side').textContent, meta: e.querySelector('.muted').textContent }));
    ok(`[${scheme}] card shows politician, side, amount, traded + filed dates`, f.name && f.hasAmt && /^(Buy|Sell|Exchange)/.test(f.side) && /Traded \d{4}-\d\d-\d\d · Filed \d{4}-\d\d-\d\d/.test(f.meta), JSON.stringify(f));
    ok(`[${scheme}] filing links are https and point to official sites`, await page.$$eval('#trade-list a.card', as => as.length > 0 && as.every(a => /^https:\/\/(disclosures-clerk\.house\.gov|efdsearch\.senate\.gov)\//.test(a.href) && a.rel.includes('noopener'))));
    await page.screenshot({ path: `${OUT}/digest-${scheme}.png` });
    // search by ticker and politician
    const tk = data.trades.find(t => t.t && t.c === 'House').t, who = data.trades[3].p.split(' ').pop();
    await page.fill('#tq', tk);
    ok(`[${scheme}] ticker search "${tk}" narrows list`, await page.$$eval('#trade-list .card', (e, t) => e.length > 0 && e.every(c => c.querySelector('.tr-as').textContent.toLowerCase().includes(t.toLowerCase())), tk));
    await page.fill('#tq', who);
    ok(`[${scheme}] politician search "${who}"`, await page.$$eval('#trade-list .card', (e, w) => e.length > 0 && e.every(c => (c.querySelector('.tr-name').textContent + c.querySelector('.tr-as').textContent).toLowerCase().includes(w.toLowerCase())), who));
    await page.fill('#tq', 'zzzqq'); ok(`[${scheme}] no match message`, (await page.textContent('#trade-list')).includes('No trades match'));
    await page.fill('#tq', '');
    await page.click('[data-f="chamber:Senate"]'); ok(`[${scheme}] Senate filter`, await page.$$eval('#trade-list .tr-ch', e => e.length > 0 && e.every(x => x.textContent.startsWith('Senate'))));
    await page.click('[data-f="chamber:Senate"]'); await page.click('[data-f="side:buy"]'); ok(`[${scheme}] Buys filter`, await page.$$eval('#trade-list .tr-side', e => e.length > 0 && e.every(x => x.textContent === 'Buy')));
    await page.click('[data-f="side:buy"]'); await page.click('[data-f="side:sell"]'); ok(`[${scheme}] Sells filter`, await page.$$eval('#trade-list .tr-side', e => e.length > 0 && e.every(x => x.textContent.startsWith('Sell'))));
    const links = await page.$$eval('a.linkbtn', as => as.map(a => a.href));
    ok(`[${scheme}] link-out hub: Capitol Trades, Quiver, Unusual Whales, House, Senate`, ['capitoltrades.com', 'quiverquant.com/congresstrading', 'unusualwhales.com/politics', 'disclosures-clerk.house.gov', 'efdsearch.senate.gov'].every(h => links.some(l => l.includes(h))), links.length);
    ok(`[${scheme}] no horizontal overflow`, await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    ok(`[${scheme}] no console errors / no external requests`, errs.length === 0 && ext.length === 0, errs.concat(ext).join(' | '));
    await ctx.close();
  }
  // trades.json unreachable -> clear message, link hub still there, no crash
  let t = await mk('light', route => route.request().url().endsWith('/trades.json') ? route.fulfill({ status: 500, body: '' }) : route.continue());
  await t.page.goto(base + '#/trades'); await t.page.waitForSelector('a.linkbtn');
  ok('trades.json failure: message + link hub, no fake data', (await t.page.textContent('#trades')).includes('Could not load the trades list') && (await t.page.$$('#trade-list .card')).length === 0 && (await t.page.$$('a.linkbtn')).length === 5);
  await t.ctx.close();
  // malformed file rejected
  t = await mk('light', route => route.request().url().endsWith('/trades.json') ? route.fulfill({ contentType: 'application/json', body: '{"schema":2,"trades":[]}' }) : route.continue());
  await t.page.goto(base + '#/trades'); await t.page.waitForSelector('a.linkbtn');
  ok('unknown schema is rejected', (await t.page.textContent('#trades')).includes('Could not load') && (await t.page.$$('#trade-list .card')).length === 0);
  await t.ctx.close();
  await browser.close(); if (server) server.close();
  console.log(res.join('\n')); console.log(fails ? `${fails} FAILED` : 'ALL PASSED'); process.exit(fails ? 1 : 0);
})();
