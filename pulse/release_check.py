"""Explicit packaged release smoke check; uses only a temporary database."""
import json
from pathlib import Path
import tempfile
import threading
import time
import tkinter as tk
import urllib.request
from . import server


def run(destination):
    result = {'ok': False}
    http = None
    try:
        window = tk.Tk()
        window.withdraw()
        window.update()
        window.destroy()
        with tempfile.TemporaryDirectory(prefix='pulse-check-') as folder:
            http = server.create_service(port=0, database=Path(folder) / 'test.sqlite3')
            threading.Thread(target=http.serve_forever, daemon=True).start()
            base = 'http://127.0.0.1:' + str(http.server_port)
            with urllib.request.urlopen(base + '/api/about', timeout=5) as response:
                about = json.load(response)
            with urllib.request.urlopen(base + '/', timeout=5) as response:
                assert b'About Pulse' in response.read()
            with urllib.request.urlopen(base + '/about-ui.js', timeout=5) as response:
                assert b'loadAbout' in response.read()
            assert about['database'] == str(Path(folder) / 'test.sqlite3')
            assert (server.ROOT / 'packaging/pulse.ico').is_file()
            # Allow the real collector to produce its first reading.
            for attempt in range(30):
                with urllib.request.urlopen(base + '/api/metrics', timeout=5) as response:
                    metrics = json.load(response)
                if metrics.get('memory'):
                    break
                time.sleep(0.3)
            assert metrics.get('memory'), 'Collector produced no metrics'
            http.shutdown()
            server.store.close()
            http.server_close()
            http = None
            result = dict(ok=True, version=about['version'], nativeWindow=True, assets=True, database=True, metrics=True)
    except Exception as error:
        result['error'] = repr(error)
    finally:
        if http:
            http.shutdown()
            server.store.close()
            http.server_close()
        Path(destination).write_text(json.dumps(result, indent=2), encoding='utf-8')
    return 0 if result['ok'] else 1
