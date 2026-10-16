# JD's Toolkit on iPhone

JD's Toolkit (unofficial, fan-made) has an iPhone version: a **Progressive Web App (PWA)** that lives in this repo under `docs/`
and is hosted by GitHub Pages.

**Live URL:** <https://geek4945-creator.github.io/matty-tools-directory/>

It has the same features as the Android app: category cards with counts, category screens, search across every tool,
use/tag filters, saved favorites, recently opened, share, NEW badges, light/dark/system theme, an About screen
(credit to Matty McTech + the "unofficial fan-made" notice) and Settings with **Check for updates now** and the last-checked date.
It works offline and has no account, ads or analytics.

> **Testing note.** The web app was tested in desktop Chrome emulating an iPhone (screen size, touch and iPhone user agent).
> It has **not** been run on real Safari or a real iPhone by its author. If something looks off on your phone, that is useful to know.

---

## 1. Install on iPhone (Safari "Add to Home Screen") - free, takes a minute

You must use **Safari** (on iPhone, only Safari can add a web app to the Home Screen; Chrome/Firefox on iOS 16.4+ can too from their Share menu, but Safari is the safe choice).

1. Open Safari on the iPhone and go to <https://geek4945-creator.github.io/matty-tools-directory/>.
2. Tap the **Share** button (square with an arrow pointing up; at the bottom, or top right on iPad).
3. Scroll down and tap **Add to Home Screen**. (If you do not see it, scroll to the bottom of the list and tap **Edit Actions**, or make sure you are not in a private tab.)
4. Leave the name as **JD's Toolkit** (or rename it) and tap **Add**.
5. Open **JD's Toolkit** from the Home Screen. It opens full screen like an app.

Tips
- Open it once with a connection so the catalog and app files are saved; after that it opens offline.
- Your favorites, recents, theme and the downloaded catalog are stored **on that device, inside that Home Screen app**.
  The Safari tab and the Home Screen app keep **separate** storage, so star things in the Home Screen app, not in the Safari tab.
- Deleting the Home Screen icon deletes its saved data. There is no cloud sync (and no Android <-> iPhone sync).
- To update the app files themselves: close the app fully (swipe it away) and reopen it with a connection.

### How updates work on iPhone (honest version)
- Android uses a background job plus a notification once a month. **iPhone web apps cannot do that reliably**:
  they cannot run silent background jobs, and web push is limited and unreliable.
- Instead, the app checks the public `catalog.json` on GitHub **when you open it**, if the last check was more than about 30 days ago,
  and any time you tap **Settings -> Check for updates now**.
- When new tools are found you get an in-app banner, "N new tools added", and the new tools get a **NEW** badge for 30 days
  (the badge goes away when you open the tool). There is no notification if you do not open the app.

### Known limits of the web app on iPhone
- No notifications and no background refresh (see above).
- Tools open in Safari (a new tab), not in an in-app browser. Close the tab / swipe back to return.
- Not in the App Store, so it will not show up in App Store search.
- Storage is per Home Screen app and can be cleared if you remove the app. (Safari may also clear website data for sites you have not opened in a long time; Home Screen apps are exempt from that 7-day rule, plain Safari tabs are not.)
- Safari/Web Share: the Share button opens the iPhone share sheet. If it is unavailable the link is copied instead.

---

## 2. Optional: a real native app via Capacitor (TestFlight / App Store)

This wraps the same `docs/` web app in a native iPhone shell. It needs:

- a **Mac** with **Xcode** (current stable version; check the Capacitor docs for the exact minimum Xcode/macOS for the Capacitor version you install),
- **Node.js** (LTS) on that Mac and CocoaPods or Swift Package Manager (Capacitor's current iOS template tells you which),
- an **Apple Developer Program** membership (**$99 USD/year**) to use **TestFlight** or publish to the **App Store**.
  Without the paid account you can still run it on your own iPhone through Xcode with a free personal team, but the install expires after 7 days and you cannot use TestFlight.

These steps were written from Capacitor's documented workflow; they have **not** been run (there is no Mac here), so expect small differences.

### A. Create the wrapper
```bash
git clone https://github.com/geek4945-creator/matty-tools-directory.git
cd matty-tools-directory
npm init -y
npm install @capacitor/core @capacitor/ios
npm install -D @capacitor/cli
npx cap init "JD's Toolkit" com.geek4945.jdstoolkit --web-dir docs
```
This creates `capacitor.config.json` with `"webDir": "docs"`. Use your own reverse-domain bundle id if you prefer;
it must be unique and cannot be changed later for the App Store listing.

### B. Add iOS and sync
```bash
npx cap add ios        # creates the ios/ Xcode project
npx cap sync ios       # copies docs/ into the app; run again after every change to docs/
npx cap open ios       # opens Xcode
```
(Do not commit `node_modules/`. Committing `ios/` is optional; add `node_modules/` to `.gitignore` first.)

### C. Configure in Xcode
1. Select the **App** target -> **Signing & Capabilities**. Tick **Automatically manage signing** and pick your **Team** (your Apple Developer account).
2. Confirm **Bundle Identifier** (`com.geek4945.jdstoolkit`), **Display Name** (JD's Toolkit), **Version** (1.0.1) and **Build** (1, increase for every upload).
3. App icon: open `App/Assets.xcassets/AppIcon` and set a **1024x1024 PNG, no transparency**. You can enlarge `docs/icons/icon-512.png` or re-export the design at 1024.
4. Choose an iPhone simulator at the top and press **Run** to test. Check: the catalog loads, favorites persist, Share works, and tapping a tool opens the site.
   In a native wrapper, links with `target="_blank"` may not open on their own. If a tool link does nothing, run
   `npm install @capacitor/browser && npx cap sync ios` and change the tool-link click handler in `docs/app.js` to call `Browser.open({ url })`.
5. Note: the service worker (offline cache) does not run inside the native wrapper; that is fine, because all files are bundled in the app itself. The catalog update check still works, because it is a normal `fetch` of the public GitHub file.

### D. Test on your iPhone
1. Plug the iPhone in, trust the Mac, enable **Settings -> Privacy & Security -> Developer Mode** on the phone (it asks for a restart).
2. In Xcode choose your iPhone as the run destination and press **Run**. On first install, trust your developer certificate in **Settings -> General -> VPN & Device Management**.

### E. TestFlight (beta testing, needs the $99 membership)
1. In [App Store Connect](https://appstoreconnect.apple.com) -> **Apps** -> **+** -> **New App**: platform iOS, name "JD's Toolkit" (the name must be unique; add a suffix if taken), primary language, the same Bundle ID, any SKU.
2. In Xcode choose **Any iOS Device (arm64)** as destination, then **Product -> Archive**.
3. In the Organizer window select the archive -> **Distribute App** -> **App Store Connect** -> **Upload**. Keep the defaults (automatic signing).
4. In App Store Connect open the app -> **TestFlight**. After processing (minutes to an hour) answer the export-compliance question (the app only uses standard HTTPS, so it normally qualifies for the exemption; answer truthfully).
5. Add **Internal Testers** (up to 100 people on your App Store Connect team; no review) or **External Testers** (up to 10,000 people by email or public link; the first build needs a short Beta App Review).
6. Testers install Apple's **TestFlight** app, accept the invite and install JD's Toolkit. TestFlight builds expire after 90 days.

### F. Publish to the App Store (optional)
1. In App Store Connect -> the app -> **App Store** tab: add screenshots (the sizes it asks for), description, keywords, support URL, privacy policy URL, category (e.g. Utilities), age rating. For App Privacy, the app collects no data.
2. Select the uploaded build and press **Add for Review** -> **Submit**.
3. Things that can get it rejected, so plan for them:
   - **Minimum functionality / "repackaged website" (guideline 4.2).** Apple can reject apps that are only a wrapped website. Add some native feel (for example native share sheet, haptics, or an offline-first design) and explain it in the review notes.
   - **Name and content.** This is an unofficial fan-made index of someone else's newsletter. Use a name that does not look official (it does not use "Matty McTech" in the app name), keep the "unofficial" notice, and consider asking Matty for permission before a public listing.
4. If rejected, answer in Resolution Center, fix, bump the Build number and upload again.

### Costs and effort in short
| Route | Cost | Needs | Where you get it |
|---|---|---|---|
| Add to Home Screen (PWA) | free | iPhone + Safari | already live |
| Run on your own iPhone via Xcode | free (7-day installs) | Mac + Xcode | Capacitor steps A-D |
| TestFlight / App Store | $99/year | Mac + Xcode + Apple Developer account | Capacitor steps A-F |

---

## Maintaining the web app (for the repo owner)
- Web app files: `docs/index.html`, `docs/app.js`, `docs/style.css`, `docs/sw.js`, `docs/manifest.webmanifest`, `docs/icons/`.
- `docs/catalog.json` is the **bundled offline snapshot**, a copy of the root `catalog.json`. The monthly GitHub Action refreshes it together with the root file.
  Installed copies fetch the live `catalog.json` from `raw.githubusercontent.com` themselves, so they do not need a redeploy to see new tools.
- Pages is served from branch `main`, folder `/docs`. A push to `docs/` redeploys it (takes about a minute).
- To change what gets cached offline, edit the `SHELL` list and bump `CACHE` in `docs/sw.js`.
- Local test: `cd docs && python3 -m http.server 8000`, then open <http://localhost:8000/> (service workers work on localhost).
