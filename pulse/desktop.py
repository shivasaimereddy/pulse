"""Windows desktop lifecycle for the standalone release."""
import json
import logging
from logging.handlers import RotatingFileHandler
import threading
import urllib.error
import urllib.request
import webbrowser
import tkinter as tk
from tkinter import messagebox

from . import __version__
from . import server

URL = 'http://127.0.0.1:8765'


def existing_service():
    try:
        with urllib.request.urlopen(URL + '/api/about', timeout=2) as response:
            info = json.load(response)
        return info.get('name') == 'Pulse' and isinstance(info.get('version'), str)
    except (OSError, ValueError, urllib.error.URLError):
        return False


def main():
    root = tk.Tk()
    root.withdraw()
    try:
        server.DATA_ROOT.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(server.DATA_ROOT / 'pulse.log', maxBytes=1024*1024, backupCount=2, encoding='utf-8')
        logging.basicConfig(handlers=[handler], level=logging.WARNING)
        if existing_service():
            webbrowser.open(URL)
            root.destroy()
            return
        try:
            http = server.create_service()
        except OSError as error:
            # Another launch may have won the port while we were starting.
            if existing_service():
                webbrowser.open(URL)
                root.destroy()
                return
            raise RuntimeError('Pulse could not start. Port 8765 may be in use by another application.') from error
        threading.Thread(target=http.serve_forever, daemon=True).start()
        root.title('Pulse')
        root.geometry('440x330')
        root.resizable(False, False)
        root.configure(bg='#f5f5f7')
        icon = server.ROOT / 'packaging' / 'pulse.ico'
        if icon.is_file():
            root.iconbitmap(str(icon))
        tk.Label(root, text='Pulse', font=('Segoe UI', 30, 'bold'), bg='#f5f5f7', fg='#1d1d1f').pack(pady=(30, 4))
        tk.Label(root, text='Your laptop, understood.', font=('Segoe UI', 13), bg='#f5f5f7', fg='#666670').pack()
        tk.Label(root, text='Running locally  ·  Version ' + __version__, font=('Segoe UI', 10), bg='#f5f5f7', fg='#22834a').pack(pady=18)
        tk.Button(root, text='Open dashboard', command=lambda: webbrowser.open(URL), font=('Segoe UI', 12), bg='#0071e3', fg='white', activebackground='#005bb7', activeforeground='white', relief='flat', cursor='hand2', padx=32, pady=10).pack()
        closing = False

        def quit_app():
            nonlocal closing
            if closing:
                return
            if server.scan.get('running') or server.wsl_storage.state.get('scan', {}).get('running'):
                if not messagebox.askyesno('Quit Pulse?', 'A storage scan is running. Quit and stop the scan? Saved results will be kept.'):
                    return
            closing = True
            quit_button.config(state='disabled', text='Saving and closing…')
            server.scanner.cancel.set()
            def stop():
                try:
                    http.shutdown()
                    server.store.close()
                    http.server_close()
                finally:
                    root.after(0, root.destroy)
            threading.Thread(target=stop, daemon=True).start()

        quit_button = tk.Button(root, text='Quit Pulse', command=quit_app, font=('Segoe UI', 11), bg='#f5f5f7', fg='#666670', relief='flat', cursor='hand2')
        quit_button.pack(pady=12)
        tk.Label(root, text='Closing this window stops monitoring.', font=('Segoe UI', 9), bg='#f5f5f7', fg='#666670').pack()
        root.protocol('WM_DELETE_WINDOW', quit_app)
        root.deiconify()
        webbrowser.open(URL)
        root.mainloop()
    except Exception:
        logging.exception('Pulse desktop startup failed')
        messagebox.showerror('Pulse could not start', 'Please close other Pulse instances and try again. Details are in ' + str(server.DATA_ROOT / 'pulse.log'))
        root.destroy()


if __name__ == '__main__':
    main()
