# Pulse

A local laptop dashboard for live resource monitoring, process inspection, storage exploration, saved scan comparisons, and performance history.

## Run

Requires Python 3.9+ on Windows. From this folder:

```powershell
python -m pip install -r requirements.txt
python -m pulse
```

Open http://127.0.0.1:8765 or double-click **Start Dashboard.cmd**. The existing `python server.py` command remains supported.

## Project layout

| Location | Responsibility |
| --- | --- |
| `pulse/` | Python application package and backend services |
| `static/` | Browser interface: HTML, styles, and feature scripts |
| `tests/` | Backend regression tests and frontend initialization checks |
| `docs/` | Architecture and detailed product documentation |
| `data/` | Private SQLite metrics and storage scans; excluded from source control |
| `server.py` | Compatibility launcher |

## Verify

Run from the project root:

```powershell
python -m unittest discover -s tests -p "test_*.py"
node tests/test_ui_boot.js
node tests/test_about.js
```

Tests use temporary databases and mock destructive system actions.

See [Architecture](docs/architecture.md) for module boundaries and [Product guide](docs/product-guide.md) for features, retention, and operational details.

## Distribute as a Windows application

See [Distribution](docs/distribution.md) for the portable `Pulse.exe`, build instructions, local data paths, and release checks. End users do not need Python or the source folder.

## Product website

The domain-ready product page lives in `website/`. See [Website setup](website/README.md) for building the upload bundle, configuring domain metadata, and updating release downloads.

Generated executables, release archives, deployment output, local databases, and build environments are excluded from Git. Build release files from the committed source using the documented scripts.
