# Pulse product website

A standalone, responsive website for hosting on your own domain. Plain HTML, CSS, JavaScript, and SVG; no Node.js build, database, external fonts, analytics, or third-party scripts.

## Build and preview

From the project root:

```powershell
python scripts/build_website.py
python -m http.server 8787 --bind 127.0.0.1 --directory website/dist
```

Open http://127.0.0.1:8787. Build the desktop release first if `dist/Pulse.exe` and the matching versioned ZIP are missing. The website builder verifies that their executable hashes match and derives the version, size, and checksums from the actual release.

You can also double-click `scripts/Preview Website.cmd` to build and open the local preview. Keep its terminal open while previewing and close it when finished.

## Host on your domain

Upload the **contents** of `website/dist/` to your static host's public directory, or extract `dist/Pulse-website.zip` there. `index.html` should be at the web root. All asset and download URLs are relative, so hosting under a subdirectory also works. Use HTTPS on your domain.

The public site offers EXE downloads only, with per-version SHA-256 checksums and third-party notices. `downloads/Pulse.exe` remains a latest-version compatibility alias. The generated `Pulse-website.zip` is an operator deployment archive, not a visitor download. Confirm your host allows executable downloads and supports their size. Static hosts with a small file-size limit may require GitHub Releases or another download host; update the link strategy in `scripts/build_website.py` when moving downloads externally.

## Update

Edit content in `website/src/`. The public tour is rendered with native HTML and SVG in `demo.js` and `demo.css`, not enlarged screenshots. It includes overview readings, grouped apps and inspection, a proportional storage map with sample folder navigation, historical graph exploration, and scan comparisons. Every reading is fictional and the tour never calls the app service, scans files, or reads visitor device data. A visible caption explains that the tour simplifies some app features.

One complete interactive tour appears in the hero. Later feature sections link to its relevant screens rather than repeating the dashboard. Simulation updates only visible overview panels while the page is active, honors pause and reduced-motion preferences, and holds readings while a graph is being explored. Graphs support pointer interaction and arrow/Home/End keys. The page uses a two-row navigation layout on narrow screens rather than scaling or cropping a desktop screenshot.

The builder replaces only the validated, generated `website/dist` directory and excludes unused legacy preview artwork and styles. Do not place source files or hand-edited deployment files in that directory.

`website/site.config.json` contains the public site URL. `website/releases.json` lists available stable releases and their notes. The product page has no public-source links or implementation-stack marketing.

For each release:

1. Bump `pulse.__version__` to a new major.minor.patch version, then build the Windows release. Its build receipt binds the version to the EXE hash.
2. Add that version and its release notes to `website/releases.json`; retain older entries you still offer.
3. Run the website builder. It archives the current EXE and notices under `release-artifacts/<version>/`, verifies all listed historical artifacts, then generates the selector, release history and `releases.json` manifest.
4. Upload the new website bundle. It contains every listed version at a permanent `downloads/<version>/Pulse-<version>-Windows-x64.exe` URL.

**Back up `release-artifacts/` separately.** Binaries are intentionally ignored by Git. Rebuilding on another machine requires copying this retained archive first (or setting `PULSE_RELEASE_DIR` to its location). A build fails if an older listed artifact is missing or changed; it never silently removes earlier downloads. Published versions are immutable: a different EXE requires a new version number. Do not rebuild an already archived version with changed code.

For Nginx, versioned download paths can use long immutable cache headers. Keep `index.html`, `release.json`, `releases.json`, and the unversioned `downloads/Pulse.exe` alias uncached or revalidated so updates appear promptly. The selected-version EXE name, size and verification hash update together. Only real archived versions are listed; there are no placeholder future releases.

 Source changes do not automatically modify the hosted website or executable. No auto-update service is claimed.

## Hosting metadata

The public URL is configured as **https://pulse.infyss.com/**. The builder generates an absolute canonical URL, Open Graph and Twitter metadata, a sitemap, and structured application data in the initial HTML. Social crawlers do not need to execute JavaScript.

The WhatsApp/social card uses `assets/social.png`, exported at 1200 by 630 pixels. The builder publishes a content-hashed copy and references its absolute HTTPS URL in the metadata, so new artwork receives a new URL. Editable artwork is in `assets/social.svg`; update it through `scripts/generate_social_preview.py` and re-export the PNG when redesigning the card. The public page and image must be reachable without authentication after uploading. WhatsApp may cache earlier cards.

## Verification

```powershell
python -m unittest tests.test_website -v
node --check website/src/main.js
node tests/test_website_demo.js
node tests/test_website_theme.js
node tests/test_website_checksum.js
```

The design includes responsive layouts, keyboard-operable demo navigation and graph exploration, native FAQ disclosures, reduced-motion support, image dimensions, and fallback links for downloads and checksums. Dark is the default appearance. The header theme button switches to light; an explicit choice is stored locally and restored before styles paint. Blocked browser storage still allows switching within the page. Social previews retain the dark product artwork.

Run `node tests/test_website_theme.js` to check theme defaults, persistence, early restoration, cross-tab updates, and blocked storage. Check desktop and mobile browsers before public launch.

`node tests/test_website_checksum.js` checks generation of Windows verification commands, published hashes, selected-version EXE metadata, clipboard fallback, and modal controls. The compact dialog provides a PowerShell command that prints MATCH or DOES NOT MATCH on the visitor's computer. It does not select, read, upload, or execute a file in the browser. The expected hashes come from the actual bundled downloads.

The hero has a rounded display frame and base without perspective transforms on its text. All demo labels remain native browser text. Verify the tour at laptop, tablet and phone widths, including navigation labels, app details, graph tooltips, folder navigation, largest files, history periods, location comparisons, and both themes.

Run `python -m unittest tests.test_website_releases` for retained versions, mutation rejection and integrity checks; `node tests/test_website_release_ui.js` covers version-selection synchronization.

The hero includes three verified principles and a static vector poster until the interactive tour mounts. With scripting unavailable, its noscript explanation, product content, release notes and direct EXE links remain usable. A single release is displayed as a plain version label; the builder reveals the selector automatically when two or more releases are listed. Product copy uses PC consistently. No analytics are added.
