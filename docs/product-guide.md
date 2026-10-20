# Pulse — Laptop dashboard

A local Windows laptop monitor with an Apple-inspired light interface, live CPU and memory history, sortable processes, drive capacity, battery and network activity, and a user-folder storage scanner.

## Act on your readings

The Improve performance page explains current resource alerts and offers actions. Processor alerts require an average of at least 75% over five or more readings, memory alerts trigger at 80%, drive alerts at 85% full, and battery alerts at 25% or lower while unplugged. These are transparent heuristics, not a hardware health diagnosis.

- Open Windows Storage settings to review cleanup, Startup settings to manage sign-in apps, Power settings, and Installed apps.
- Scan your user folder and select Review to open a folder in File Explorer. Review and delete files yourself using Windows.
- End an eligible process after an explicit confirmation. This can lose unsaved work. Windows processes, the monitor and its ancestors, other users' processes, and inaccessible processes are protected. The backend rechecks identity and eligibility before termination.

Actions require a session token and reject outside origins. No files are automatically deleted and no settings are automatically changed.

## Run

Requires Python 3.9 or later. Install dependencies with `python -m pip install -r requirements.txt`, then double-click **Start Dashboard.cmd**. Alternatively run `python server.py` and open http://127.0.0.1:8765. Keep the terminal running while using the dashboard; Ctrl+C stops it.

The service listens only on your laptop's loopback address. No account or administrator access is required. The interface uses system fonts and works offline. Metrics and file paths stay local.

## Notes

- Metrics update every two seconds. CPU percentages per process are normalized across logical processors. The first process sample establishes a baseline.
- The live Overview chart shows the last three minutes. The separate History page persists readings across service restarts.
- Storage scans are manual and support the user folder, common locations, connected local volumes, and a custom local path. Scans skip links/reparse points and report inaccessible entries. Sizes are logical file sizes, which can differ from physical allocation, particularly with cloud or compressed files. Pulse never deletes files.
- Some protected processes and hardware sensors are unavailable without additional system support. Temperature, GPU usage, and per-app network traffic are not collected by this version. Battery data appears only when the operating system exposes it.
- Run action API tests with `python -m unittest discover -s tests -p "test_*.py"`. Tests mock all launch and termination actions.

## Local history

Pulse stores its database at `data/pulse.sqlite3` in the project root. SQLite is included with Python: no extra service, account, or dependency is needed. The data directory is excluded from Git and is outside the served static directory.

- Live readings update every two seconds. A bounded queue sends compact summaries to a background writer, which commits a batch every ten seconds using SQLite transactions and WAL. Orderly shutdown flushes pending readings; a forced shutdown can lose the last unsaved batch.
- Minute averages and peaks are kept for seven days; hourly aggregates are kept for 365 days. The one-year view groups hourly records into daily averages and preserves peaks, limiting chart size. Queries use the resolution/time primary key.
- App usage is grouped by executable name and summarized hourly for 30 days. It saves resource totals, sample counts, and peak memory, rather than full process dumps, PIDs, executable paths, or command lines. App averages cover samples where the app was present; they are not a percentage of the entire selected period. App queries include whole hours overlapping the selected range.
- Up to 20 completed folder-scan results are saved locally, including their file/folder paths, and the latest scan is restored at startup.
- Expiration runs at startup/first flush and then hourly. SQLite reuses freed pages, so the database file may retain its high-water size rather than shrinking immediately. The History page reports actual database and journal storage usage.
- History starts when this version runs; past readings cannot be reconstructed. No readings are invented while the laptop is off, asleep, or the service is stopped. Browser closure and display pause do not stop the background recorder.
- History reads do not block metric collection. Failed writes are retried through the bounded queue; prolonged failures can skip samples, which are reported on the History page.

Open **History** and choose one hour, 24 hours, seven days, 30 days, or a year. The chart can show processor/memory, network speed, aggregate free disk space, and battery. The cards show sample-weighted averages, peaks, and free-space change between saved buckets. Gaps represent missing saved buckets; partial buckets are included. Refresh is automatic every 30 seconds while viewing History, with a manual refresh button as well.

Run the backend regression suite with `python -m unittest discover -s tests -p "test_*.py"`. Storage tests use temporary databases only.

## Storage explorer and WSL

Storage now separates Windows drive capacity from WSL/Linux filesystems. The Windows total already includes WSL virtual disk files; Linux capacities and `/mnt/c` are never added to it. Mounts are labelled as Windows aliases, shared Linux root mounts, or additional filesystems. The History free-space chart remains Windows-volume free space, not a combined Windows + Linux total.

WSL inventory reads the current user's registered distributions and VHD metadata. It shows host-allocated bytes (via the Windows allocation API), file length, and Linux `df` capacity separately. It also checks the standard Docker Desktop data-VHD locations, which can be separate from its registered distro VHD. Custom Docker disk-image locations are not automatically discovered. A missing VHD or denied permission is shown as unavailable.

WSL checks run on a separate background worker, are cached for one minute, and probe only distributions listed as running. Stopped distributions remain stopped in normal operation; if a distribution stops between the running-state check and the read command, WSL itself may restart it. Reading Storage does not run a recursive Linux scan. The explicit Analyze Linux folder action uses `du -x` for `/home`, `/var`, `/usr`, or `/opt`, without sudo, with a 90-second timeout. Results use allocated bytes and can be incomplete where access is denied. Linux folder-scan results are session-only; Windows completed scans continue to be saved in local history. Review opens Linux folders through `\\wsl.localhost\<distribution>`, never by editing the VHD file.

Windows folder scans support cancellation, folder drill-down, largest files, name/extension search, size filters, and sorting. The scanner retains only the 500 largest immediate children and 50 largest individual files to bound result memory and persisted payloads. Windows logical file sizes can count hard-linked content at each path; they are not a physical-allocation audit. Partial/cancelled scans are labelled and do not replace the last completed saved scan. A file's Review button opens its parent folder in Explorer. System folders can be measured if the current account has read access; Pulse does not request elevation itself.

Cleanup options open Windows' own Storage or Installed apps settings for review. Pulse does not compact VHDs, prune Docker volumes, or delete files automatically. See [Microsoft's WSL disk-space documentation](https://learn.microsoft.com/en-us/windows/wsl/disk-space).

Run all checks with `python -m unittest discover -s tests -p "test_*.py"`.

## Apps, processes, and identity

Apps & processes offers grouped apps and individual Windows processes, sorting by CPU/memory/name/start time, search by name/script/executable path/PID, and filters for your apps, Windows/services, heavy users, and processes eligible to manage. Groups use executable location plus a Python/Node script or module identity when readable. Different projects with the same script basename remain separate when their locations differ. These labels are derived from observed names and commands, not verified publisher signatures or security ratings.

The inspector identifies the selection using **PID and creation time**. It reads the executable, command line, working folder, Python/Node task, account, parent/children, thread/handle counts, and cumulative read/write I/O counters on demand. Unreadable fields are explicitly marked unavailable. CPU and working-set memory update from the live sample; other dynamic counters refresh every six seconds. Refresh details updates the full identity and relationships. Charts in the inspector are temporary and cover samples observed while it is open. They are not historical per-PID recordings.

Python and Node identity labels are cached once per process lifetime. On 64-bit Windows, the high-frequency collector reads CPU time, working-set memory, and process names in a single bounded system snapshot per interval. This avoids the repeated full-system queries triggered by legacy psutil lookups for protected processes. It uses a read-only [Windows system-information query](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntquerysysteminformation), with record bounds checks, a 64 MB allocation cap, and a psutil compatibility fallback. Process actions still use exact psutil PID/start-time validation. Commands, accounts, and parent maps are not fetched repeatedly in the sampling loop. Pulse labels its own Python service **Pulse monitor**, with `server.py` and an explanation of why it cannot be stopped from its own UI.

The inspector can open the executable/script/working folder, inspect parent and child processes, copy a process report, and request termination of one eligible process after confirmation. It revalidates PID/start time and permissions before actions. It does not end an entire app group or process tree. Task Manager opens the fixed Windows system executable. The CSV snapshot includes the filtered individual processes, with spreadsheet-formula escaping and without command lines.

Command lines are displayed locally after best-effort masking of recognized secret flags, key-value pairs, and URL credentials. This cannot recognize every secret format: review a report before sharing it. Commands, working folders, and full identity reports are not written to the history database. A process that already exited before inspection cannot be reconstructed from its name alone. The historical app summaries still group by executable name.

Run all backend tests with `python -m unittest discover -s tests -p "test_*.py"`. Run `node tests/test_ui_boot.js` for the script initialization smoke check; browser verification remains necessary for layout and interactions.

## Saved folder scans

Storage restores the last successful scan when selecting a previously scanned Windows folder. Scan again refreshes that location. Results survive browser and service restarts in SQLite, with up to 20 recent locations; rescanning one folder replaces its snapshot rather than consuming another location slot. Each snapshot retains up to 500 immediate children and 50 largest files. Stopped or failed scans are marked partial and do not replace a successful saved scan.

Recent scans provides quick return to custom folders. Export scan downloads both result views as CSV with scan time, paths, sizes and modified dates. Oldest modified first and Reset filters help review results. After a repeat scan, a size-change summary appears only when both scans have complete child listings and no unreadable entries; it compares listed logical bytes, not physical disk space reclaimed. WSL analysis remains separate and is not part of Windows saved-folder history.

## Browse a saved scan

New Windows scans build a folder hierarchy in the same filesystem traversal. Opening a folder or moving up uses saved results, with the original scan timestamp. Largest files is scoped to the folder being browsed. Only Scan location / Scan again reads the filesystem again. Earlier snapshots need one explicit rescan to populate the hierarchy.

The browsing index is compressed separately in SQLite and fetched one folder at a time; it is not included in live polling or the recent-scans response. Each folder retains up to 500 immediate children and its 50 largest descendant files. The total index budget is 100,000 retained records per scan (plus the bounded root summary). When this limit omits a folder, the UI explains that an explicit scan is needed rather than silently scanning it. Indexes expire with their parent snapshot and Delete scan history removes them. Scan options contains recent scans, custom locations, export and history deletion; Filter & sort contains search, size and ordering controls.

## Storage Changes

Changes compares the latest two successful snapshots of the same scan location. It shows net logical-size change, increases, decreases, and up to 200 largest changed immediate entries. Individual files additionally compares direct file listings in nested folders present in both browsing indexes. File details are limited to comparable saved listings; it does not claim a complete file audit or detect same-size edits. Newly added or entirely removed folders appear as folder changes; their descendants are not all expanded as individual file changes.

Comparisons are calculated when saving a scan, and only compact differences are retained alongside the newest snapshot. No second filesystem traversal or background rescan is triggered. Comparisons are unavailable when either root listing is capped or has read errors. A missing path may have moved or been renamed, so the UI says no longer listed and opens the scan location for review. Clearing scan history also removes comparisons. Performance changes are not part of this first Changes view.

## Complete saved browsing index (current)

New scans stream every readable file and directory to a temporary disk-backed index in batches of 512, then atomically replace the saved snapshot in SQLite. The former 100,000-record retention cap no longer applies. Cancellation, persistence errors, or interruption do not replace a successful saved snapshot. The scan remains busy while its index is being committed, without holding the live-metrics lock.

Indexed lookups load 200 immediate children at a time. Show more saved results loads the next page; name search, minimum size, and sorting run against all saved children. Each folder retains its 50 largest descendant files as a compact summary. Root summaries used for live progress remain bounded; the backing index retains all readable entries. Export displayed results exports the currently loaded child rows plus the largest-files summary.

Older capped/compressed snapshots remain readable where details exist. Missing details explicitly identify the old snapshot and offer Refresh original scan. One explicit rescan is required to recover details the old version never retained. New index rows and comparisons expire with their snapshot or Delete scan history. These rules supersede the earlier capped-tree notes above. Two fully indexed scans can compare all saved entries, including folders with more than 500 immediate children.

Scan records use fixed-size path identifiers, with file names and sizes stored once and folder summaries compressed. Full paths are reconstructed from the saved parent folder when browsing. Existing full-row indexes are migrated and compacted on startup without rereading user files; older capped trees still need a rescan to recover omitted data.

## Storage view continuity

Within each browser tab, reload restores the selected storage folder, source snapshot, Windows/WSL pane, Folder contents/Largest files view, search text, minimum size and sort order. Switching result views reuses the current folder response when the query is unchanged, including already-loaded pages. Filtering preserves the current data during loading and commits only the newest navigation response. Idle polling does not replace a loaded folder or interfere with an in-flight browse request.

Reload now shows a small loading transition before revealing the saved screen. Initial metrics and the selected screen data settle before scroll restoration and reveal, avoiding an Overview flash or a jump while folder rows load. Scroll position is saved per screen in the current browser tab. Reduced-motion preferences are respected, and an eight-second fallback reveals the connection status rather than leaving the loading overlay indefinitely.

## Performance Insights

Improve performance includes a local activity timeline for the last hour, 24 hours or seven days. CPU at 75% or memory at 80% must remain high across sampled observations for at least 60 seconds, with at least 25 samples and 80% nominal sample coverage, before a period is recorded. A below-threshold sample ends the period; sample gaps over ten seconds, backwards clock changes and service restarts separate observations. The screen describes observed pressure, not a diagnosis or proof of a slowdown.

The background history writer persists minute CPU/memory summaries and compact candidate app summaries for seven days, plus up to 2,000 pressure periods for 30 days. The UI returns at most 200 recent periods within the chosen range and reports truncation. Each period retains the five highest observed CPU or memory users, from a bounded set of 64 candidate app groups. Group IDs are hashes; friendly labels and executable names are saved, with no process IDs, command lines, working directories or executable paths. Minute candidate app summaries retain up to twenty leaders, not every app.

App averages are across all event samples, including zero while absent or outside the retained candidate set. Repeated-app counts merge overlapping CPU and memory periods so the same busy moment is not counted twice. The event CPU and memory duration cards may overlap; they are not total wall-clock slow time. Recording starts with this release; older hourly app history cannot be used to reconstruct events. Updates are batched with the history transaction, and detector state advances only after a successful commit.

Review app opens matching current processes and explains that historical processes may have exited. It does not automatically terminate anything. Windows settings links are suggestions for review. Performance Insights refreshes every 15 seconds while visible; the period choice is remembered per browser tab.


## Local workspace improvements

### Database selection

Source launches support an explicit database path, the Windows AppData database, or a native file chooser. An explicit launch option takes precedence over the location saved in Settings. Existing databases open in place and are not copied or replaced. The executable uses the selected location on subsequent launches.

### Overview

Overview distinguishes sustained resource usage from brief spikes. Processor usage of at least 75% or memory usage of at least 80% must persist for a minute before being treated as sustained. These observations are not a hardware health score or proof of a slowdown. Paused, disconnected and delayed readings are identified.

Resource leaders group related processes and rank them by CPU or memory. System essentials shows battery, available memory, network traffic and disk read/write rates. Network traffic is not an internet speed test, and disk throughput is not disk utilization or drive health. Available memory includes reclaimable cache.

### Storage exploration

Successful scans are retained per location. Switching folders restores their saved results. Folder contents show immediate children with descendant sizes included; Largest files shows individual files found beneath the scanned location. These views overlap and their sizes must not be added together.

Saved indexes allow browsing without rescanning. A refresh explicitly scans again; incomplete or unreadable coverage is disclosed. The space map sizes tiles by logical file size. Small items may be grouped, and active filters and displayed-result limits are identified. Logical size can differ from occupied or reclaimable disk space.

Open Understand your space to explore drives and retained folder snapshots. Drive capacity is distinct from scanned folder coverage. Saved folders may overlap; Pulse never adds their totals together to estimate drive usage. Whole-drive scanning is explicit and can be stopped. Windows volume usage already includes the space occupied by WSL virtual disks.

### Activity timeline

The timeline combines sustained performance periods, retained storage comparisons and gaps in recording. Filter by type and time range, then expand an event to review its evidence. App observations during a busy period do not prove an app caused the slowdown.

Storage events link to the exact retained comparison. A recording gap represents at least two missing minute buckets after recording began. Gaps may reflect sleep, downtime or a recording problem; Pulse does not infer the cause. Earlier history cannot reconstruct missing app attribution.

### Tooltips and chart readings

Help controls explain measurements and limitations. Graphs support pointer, touch and keyboard exploration with exact timestamps and values. Gaps have no invented readings. Tooltips stay within the viewport and work inside dialogs.

### Settings

Appearance, new-session screen and display refresh belong to the browser. Refreshing restores the active screen and scroll position. The optional compact sidebar preference is remembered. Recording belongs to the selected database and is independent of display refresh or pause.

Turning off Save performance history stops persistence while keeping live monitoring and storage scans available. Pending samples are saved before pausing. Retention is bounded: seven days of minute detail, one year of hourly trends, thirty days of app summaries and busy periods, and twenty recent storage snapshots. Expired records free database pages for reuse; deletion does not necessarily shrink the file.

Performance history and storage snapshots can be cleared separately after confirmation. Actual files are not deleted. Clearing performance history while recording is enabled starts a new record immediately. Storage history cannot be cleared during a scan.

### Change the history database in Settings

Choose Settings > Change database location. Browse for an existing Pulse database or select a new filename, review the location, and choose Use this database. Use default location selects the Windows AppData location. No terminal commands are needed.

Pulse saves queued readings before switching and keeps the previous file intact. An existing database opens in place; a new file starts empty. Databases are not merged. Switching is blocked during storage scans. The location is remembered for future launches, and open dashboard tabs reload to avoid mixing history from different databases.

Existing files are inspected read-only for a compatible Pulse schema before opening. Unrelated files and databases from a newer version are rejected. If saving the current history or recording the location preference fails, the active database stays selected.

Performance history focuses on saved readings and app activity. Retention, database size and recording behavior are described in Settings. Closing the browser leaves Pulse running; quitting Pulse stops recording. Pausing live updates only freezes the display.


### Focused page layouts

Settings separates Appearance & display, Recording, and Manage data into keyboard-accessible tabs. The selected section is restored within the browser session. Database controls remain available alongside the selected section. About contains the app version, local recording state and expandable installation details; retention controls remain in Settings.

On wide screens, Storage places the space map beside the saved contents list. Narrow screens stack them. Largest files uses the full results width. The saved contents list keeps its scroll position across refresh and returns to the top for a new folder or result view. Folder navigation continues to use retained indexes without automatically scanning.

Measurement explanations on Processes, Insights and Storage changes expand on demand. Summary labels and empty states distinguish retained data, incomplete coverage and missing observations without inventing measurements.
