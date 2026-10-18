# Architecture

Pulse runs one local Python HTTP service and serves a plain JavaScript interface. There is no frontend build step or separate database service.

## Backend boundaries

- `pulse/server.py`: HTTP endpoints, session protection, live sampling orchestration, and application lifecycle. `main()` binds only to localhost.
- `pulse/history_store.py`: SQLite persistence, retention, scan snapshots, and historical queries.
- `pulse/performance_insights.py`: sustained resource-pressure detection and compact historical summaries.
- `pulse/storage_tools.py`: Windows folder scanning and WSL storage discovery.
- `pulse/scan_index.py`: temporary scan indexing and compact scan-entry serialization.
- `pulse/process_tools.py`: process identity, inspection, and guarded action validation.
- `pulse/process_snapshot.py`: efficient Windows process sampling with a compatibility fallback.

Internal imports are package-relative. The package entry point is `python -m pulse`; the root `server.py` remains a compatibility launcher.

## Frontend boundaries

`static/index.html` composes the screens. `app.js` owns shared state and live metrics; feature scripts implement storage, processes, scan comparisons, and insights. `navigation.js` restores the selected screen, `startup.js` gates first rendering, and `theme.js` manages appearance. Styles remain in `style.css` and `theme.css`.

## Runtime data and paths

Static files are resolved relative to the application bundle. Source runs keep `data/pulse.sqlite3` in the project; packaged Windows runs keep it under `%LOCALAPPDATA%\Pulse`, independent of executable location. The database stays outside the HTTP static directory. Moving source modules does not move or recreate saved data. Do not commit databases, Python caches, or generated previews.

## Validation and development

Run both commands documented in the root README after structural changes. Backend tests live under `tests/` and patch dependencies at their package-qualified import locations. The JavaScript check reads frontend assets from the project root and does not require a browser or extra packages.

Keep new backend behavior in the responsible module and new interface behavior in the matching feature script. Avoid adding layers or dependencies unless the feature needs them.

## Version and About

`pulse.__version__` is the single application version. Update it for a release; the About page reads it through the read-only `/api/about` endpoint alongside local installation and recording details. Version 1.0.0 establishes the initial versioned release.

## Desktop release

`pulse/desktop.py` owns the native controller, repeated-launch handling, browser opening, and clean service shutdown. `server.create_service()` provides a shared lifecycle for command-line and packaged runs. `packaging/` contains the desktop entry point, release icon, and locked build dependencies; `scripts/` contains the repeatable Windows release builder. Generated artifacts stay in ignored `build/` and `dist/` folders.
