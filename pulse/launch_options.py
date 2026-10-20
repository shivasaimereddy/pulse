"""Database selection for source launches; no persistence starts here."""
import argparse
import os
from pathlib import Path


def appdata_database():
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))) / 'Pulse' / 'pulse.sqlite3'


def choose_database(initial_database=None):
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    default = Path(initial_database) if initial_database else appdata_database()
    try:
        root.attributes('-topmost', True)
        return filedialog.asksaveasfilename(
            parent=root, title='Choose Pulse database — existing or new',
            initialdir=str(default.parent if default.parent.exists() else Path.home()),
            initialfile=default.name, defaultextension='.sqlite3',
            filetypes=[('Pulse database', '*.sqlite3 *.sqlite *.db'), ('All files', '*.*')],
            confirmoverwrite=False)
    finally:
        root.destroy()


def database_option(argv=None):
    parser = argparse.ArgumentParser(description='Pulse local dashboard. Existing Pulse databases are opened in place; they are not copied or replaced.')
    options = parser.add_mutually_exclusive_group()
    options.add_argument('--database', metavar='PATH', help='Use this Pulse SQLite database (created if missing).')
    options.add_argument('--appdata', action='store_true', help='Use the same AppData database as Pulse.exe.')
    options.add_argument('--choose-database', action='store_true', help='Open a database file picker, initially at the EXE data location.')
    args = parser.parse_args(argv)
    if args.choose_database:
        selected = choose_database()
        if not selected:
            return False
    else:
        selected = args.database or (appdata_database() if args.appdata else None)
    if not selected:
        return None
    path = Path(os.path.expandvars(str(selected))).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()
