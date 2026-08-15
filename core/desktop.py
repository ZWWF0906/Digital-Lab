from __future__ import annotations

import threading
import time
import sys
import os

from core.dashboard_server import create_app, _find_port


def launch_desktop():
    try:
        import webview
    except ImportError:
        print("[ERROR] 需要 pywebview 库，请运行: pip install pywebview")
        return

    port = _find_port(8080, "127.0.0.1")
    if port == 0:
        print("[ERROR] 端口 8080-8089 均被占用")
        return

    from core.collector import start_collector, stop_collector
    start_collector()

    app = create_app()

    def _run_flask():
        app.config["SERVER_NAME"] = None
        try:
            app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
        except OSError:
            pass

    t = threading.Thread(target=_run_flask, daemon=True)
    t.start()
    time.sleep(0.5)

    url = "http://127.0.0.1:{}".format(port)
    try:
        webview.create_window(
            "DigitalLab",
            url,
            width=1120,
            height=720,
            min_size=(860, 520),
        )
        webview.start()
    finally:
        stop_collector()
