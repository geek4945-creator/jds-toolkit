# Matty Tools Directory (unofficial)

An Android app (plus a web-friendly `catalog.json`) that collects the tools and websites featured in
**Matty's Powerful Newsletter You Should Know** by **Matty McTech** - <https://www.mattymctech.com/>.

> **Unofficial, fan-made.** Not made, endorsed or affiliated with Matty McTech or beehiiv. All credit for finding
> these tools goes to Matty. Every entry links to the post it came from. If you like the list, subscribe to the newsletter.

## What the app does
- Home screen with category cards and tool counts (12 categories + an "Uncategorized / New" bucket)
- Category screens, search across every tool, and **use/tag filters** (Free, PDF, Video, AI, Games, ...)
- Favorites, recently opened, share a tool, "New" badges on newly added tools
- Opens sites in an in-app browser (Chrome Custom Tab, falls back to your default browser)
- Light, dark or system theme; About screen with credit + unofficial notice
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
1. Download `mattymctech-tools.apk` (GitHub release page) to your phone.
2. Open it. Android will ask to allow "install unknown apps" for your browser/file manager - allow it for this install.
3. Tap Install. On Android 13+ allow notifications when prompted if you want the monthly "new tools" notice.

(Or with a computer: `adb install -r mattymctech-tools.apk`.) Verify with `apksigner verify`; the release APK is signed with the
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
- `sources.json`: optional **public** spreadsheet/CSV links to import (name/url/description/category/use/pricing/notes columns become fields and tags). Empty today - see below.
- `.github/workflows/update-catalog.yml` runs the tests and the script monthly (and on demand) and commits a changed `catalog.json`. The app's monthly check then picks it up.

### Spreadsheets
Matty's "Website list in a Google Sheet" is members-only (Patreon, from $1) according to the page title/search listing; no public sheet link exists on mattymctech.com.
Nothing was imported from it. If you get access and the owner is OK with it, export it to a CSV you may share, or add a public CSV URL to `sources.json`.

## Layout
```
update_catalog.py  catalog.json  overrides.json  manual_items.json  sources.json  tests/  .github/workflows/
android/           Gradle project (app/src/main/java/com/geek4945/mattytools/{data,ui,work}, MainActivity.kt)
```
