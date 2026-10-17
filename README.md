# JD's Toolkit (unofficial)

An Android app (plus a web-friendly `catalog.json`) called **JD's Toolkit** (repo: `jds-toolkit`): a directory of handy tools and websites, sorted by category.
The list started from Matty McTech's newsletter and public sheets; that credit (and any future ones) lives in **Settings > About > Credits**.

> **Unofficial, fan-made.** Not made, endorsed or affiliated with the people or sites credited in the app. Every tool shows where it came from on its "From:" line.

## Credits (Settings > About)
Credits are data, not code. They live in [`credits.json`](credits.json) and are copied into `catalog.json` (field `credits`), which is bundled in the Android app and the web app as a fallback and is downloaded by the monthly update check, so **new credits appear without an app update**.

To add a credit:
1. Add an entry to `credits.json`:
   ```json
   { "name": "Someone Great", "contribution": "Shared a big list of free design tools.", "url": "https://example.com/" }
   ```
   `name` and `contribution` are required; `url` is optional (must start with `http://` or `https://`).
2. Run `python3 update_catalog.py --credits-only` (no crawling; it validates the file, copies it into `catalog.json`, the Android bundle and `docs/catalog.json`, and bumps the catalog version so installed apps accept it).
3. Commit and push to `main`. Installed apps pick it up on their next monthly check (or **Settings > Check for updates now**). The next full `update_catalog.py` run / monthly GitHub Action also carries the credits along.

Per-tool source credit is separate: each tool keeps its own `sources` (shown as "From: ..." on the tool card), so a tool added from a new source can be credited there as well.

## Politician Trades digest (Money, Jobs & Business)
A card at the top of **Money, Jobs & Business** opens a digest of recent stock trades that members of Congress reported in their public STOCK Act disclosures (politician, chamber, ticker/asset, buy/sell, amount range, trade date, filing date). It has search (politician, ticker, company), House/Senate and Buy/Sell filters, a "list refreshed" stamp, and links out to Capitol Trades, Quiver Quantitative, Unusual Whales and the official House and Senate disclosure sites. It is information only, not investment advice. Filings can be made up to 45 days after a trade, so recent trades may be missing.

**Where the data comes from** (no API keys, nothing from sites that block bots):
- **House:** the Clerk's public filing index and each Periodic Transaction Report PDF at `disclosures-clerk.house.gov`, read with `pdftotext`. [`update_trades.py`](update_trades.py) is slow (one request per 0.6 s), names this project in its User-Agent, and only downloads filings it has not seen. A filing whose row count does not match the number of assets listed is left out instead of guessed. Scanned/paper filings contain no text and are skipped (the digest says how many).
- **Senate:** Senate eFD only answers after a click-through agreement in a browser session, which this project does not automate. Senate rows are copied from the community CC0 dataset [LuxAlgo/market-trackers-data](https://github.com/LuxAlgo/market-trackers-data) (which parses eFD), labelled as such with that dataset's own "as of" date. That dataset is small and was last updated on 2026-09-07 when this was built, so the Senate side is partial and may be stale. If it disappears the script keeps the last rows it had.
- Capitol Trades, Quiver and Unusual Whales are never fetched, only linked.

**How it updates:** [`.github/workflows/update-trades.yml`](.github/workflows/update-trades.yml) runs nightly, runs `python update_trades.py`, and commits `trades.json` (plus the copies in `docs/` and `android/app/src/main/assets/`) only if something changed. The apps read that static file: the Android app and the web app both try to fetch the newest copy when the digest opens and fall back to the bundled one. Run it yourself with `python3 update_trades.py` (needs `poppler-utils`). Tests: `python3 -m unittest discover -s tests` and `node tests/pwa_trades_check.js`.

**Please note:** the House Clerk and Senate eFD portals state limits on how the data may be used (for example, not for commercial purposes or soliciting money). This is a free personal tool; check those terms before reusing the data elsewhere.

## Category icons
Every category card (home) and category screen shows an icon. The artwork and the category -> icon map are data, shared by the Android app and the web app:
- [`icons.json`](icons.json) (repo root) holds the icon paths (Material Icons, Round style, Apache License 2.0, 24x24 grid, drawn as inline vectors, no downloads at runtime) and `categories` (category id -> icon name). `default` is the icon used for any category without one.
- Each category in `catalog.json` also has an `icon` field. Lookup order: the category's own `icon` -> the id map in `icons.json` -> the default folder icon. So a **new category added later** shows the folder icon, or any icon you name in its `icon` field.
- To change or add an icon: edit `icons.json` (and `CATEGORIES` in `update_catalog.py` for a new category), then run `python3 update_catalog.py --sync-icons`. It copies `icons.json` into the Android assets and `docs/`, and refreshes the `icon` fields in the catalog files (no catalog version bump). The monthly GitHub Action does the same copy.
- Headless check of the web version: `node tests/pwa_icons_check.js` (needs `playwright-core` and Chrome).

## iPhone / web version
An installable web app (PWA) lives in `docs/` and is hosted on GitHub Pages: <https://geek4945-creator.github.io/jds-toolkit/>.
On iPhone open it in Safari -> Share -> **Add to Home Screen**. It has the same features as the Android app and works offline, but iOS web apps
cannot run background jobs or send reliable notifications, so it shows an in-app "N new tools added" banner when you open it instead.
See [IOS.md](IOS.md) for install steps and the optional native App Store route (Capacitor, Mac + Xcode, $99/yr Apple Developer account).

## What the app does
- Home screen with category cards and tool counts (12 categories + an "Uncategorized / New" bucket)
- Category screens, search across every tool, and **use/tag filters** (Free, PDF, Video, AI, Games, ...)
- Favorites, recently opened, share a tool, "New" badges on newly added tools
- Opens sites in an in-app browser (Chrome Custom Tab, falls back to your default browser)
- Light, dark or system theme; About screen with data-driven Credits + unofficial notice
- **Monthly update check** (WorkManager periodic work, ~30 days, network required): downloads the public
  `catalog.json` from this repo, compares versions, merges new tools (marked **NEW**) and posts a notification
  "N new tools added". Settings has a **Check for updates now** button and the last-checked date.
- Kotlin + Jetpack Compose, minSdk 23, targetSdk 34, no accounts, no ads, no analytics.

## Important limitation - what is in the catalog
Most newsletter posts show only their **first few tools** to people who have not signed up ("Subscribe to keep reading").
This project only lists what is openly readable and **does not read, store or bypass the gated remainder**
(`update_catalog.py` stops at the post's "subscriber break"). So the catalog covers the openly visible tools of every post,
not all ~300 numbered websites. Posts that are fully open (e.g. 11-30, 51-60, 71-90, 296-301) are complete.
The newsletter's full spreadsheet, if you want it, is offered to Patreon supporters - nothing here bypasses that either.

## Install the APK
1. Download `jds-toolkit-v1.0.7.apk` (GitHub release page) to your phone.
2. Open it. Android will ask to allow "install unknown apps" for your browser/file manager - allow it for this install.
3. Tap Install. On Android 13+ allow notifications when prompted if you want the monthly "new tools" notice.

(Or with a computer: `adb install -r jds-toolkit-v1.0.7.apk`.) Verify with `apksigner verify`; the release APK is signed with the

**Updating:** open **Settings → App updates → Check for updates**. The app checks this repo's latest GitHub release (also once a day on open), downloads the APK and opens Android's installer; allow "Install unknown apps" for JD's Toolkit the first time. Same package and key, so your favorites are kept.
project's own key. A debug build installs the same way but is signed with a debug key (uninstall one before installing the other).

## Build from source
Requirements: JDK 17, Android SDK (platform 34, build-tools 34.0.0), Gradle 8.7+.
```bash
cd android
echo "sdk.dir=/path/to/android-sdk" > local.properties
gradle :app:testDebugUnitTest assembleDebug          # tests + app/build/outputs/apk/debug/app-debug.apk
# release (needs a keystore.properties with storeFile/storePassword/keyAlias/keyPassword):
gradle assembleRelease -PkeystoreProps=/path/to/keystore.properties
```

## How the catalog stays current
`catalog.json` (repo root, also bundled in the app under `android/app/src/main/assets/`) is produced by `update_catalog.py`:

```bash
python3 update_catalog.py            # crawl the live site (polite: 1.2 s between requests), merge, rewrite catalog.json
python3 update_catalog.py --dry-run  # show what would change
python3 -m unittest discover -s tests
```
- Finds posts via `sitemap.xml` + `/archive?page=N` (the site has no RSS feed).
- Extracts name, URL, short description, source post (title/date/URL) for each openly readable tool; strips tracking params and sponsor blocks.
- De-duplicates by normalised URL; existing ids are stable (favorites keep working); nothing is ever deleted; `version` is bumped only when something changed.
- **Categorisation is rule-based keywords** (`CATEGORY_RULES` in the script) with a fallback bucket "Uncategorized / New". It is a rough guess: new items may land in
  the wrong category until someone corrects them. Hand-made fixes live in `overrides.json` (category/tags, a corrected `url`, or `skip`) and always win.
- `manual_items.json`: hand-added entries taken from openly readable post text (e.g. VLC from the "Free TV" post).
- `sources.json`: **public** spreadsheets to import. Today it lists the public "Website list" Google Sheet (published to the web, 2 tabs: Powerful Websites, Cure Boredom). The script lists every tab of the published sheet itself, downloads each tab as CSV, maps number / name / link / description (and category / use / pricing / notes columns when a tab has them), skips rows without a usable web address (blank rows, donation links, links to TikTok videos, shortened links that only point to a video), and merges the rest with the newsletter tools by normalised URL, recording the sheet as an extra source.
- `.github/workflows/update-catalog.yml` runs the tests and the script monthly (and on demand) and commits a changed `catalog.json`. The app's monthly check then picks it up.

### Spreadsheets
The newsletter's *public* website list (a Google Sheet published to the web, link provided by the app's owner) is imported on every run of `update_catalog.py`,
so the monthly GitHub Action and the in-app monthly check both pick up rows Matty adds later, including new tabs.
Matty's separate members-only (Patreon) sheets are **not** read, and nothing here bypasses them. Never put a private, sign-in or paid sheet in `sources.json`.
Sheet rows are keyword-categorised like everything else; fixes go in `overrides.json` (`category`, `name`, `url`, `skip`).

## Layout
```
update_catalog.py  catalog.json  credits.json  overrides.json  manual_items.json  sources.json  tests/  .github/workflows/
android/           Gradle project (app/src/main/java/com/geek4945/mattytools/{data,ui,work}, MainActivity.kt)
```
