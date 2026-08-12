from __future__ import annotations

import logging
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

import flet as ft

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.app import StockMonitorApp  # noqa: E402


_LOG_PATH = BASE_DIR / "run_log.txt"

# Singleton logger shared by main.py and src/app.py
_logger = logging.getLogger("g360.stock_monitor")
if not _logger.handlers:
    _fmt = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
    _handler = RotatingFileHandler(_LOG_PATH, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
    _handler.setFormatter(_fmt)
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)


def _log(msg: str):
    _logger.info(msg)


def main(page: ft.Page):
    app = StockMonitorApp(page)
    page.on_close = lambda _: app.shutdown() if hasattr(app, "shutdown") else None


if __name__ == "__main__":
    _log("MAIN_START: __name__ == __main__")
    try:
        _log("PRE: llamando a ft.run(main) desktop...")
        ft.run(main, view=ft.AppView.FLET_APP)
        _log("POST: ft.run(main) retorno OK")
    except Exception as e:
        _log(f"[FATAL] Error en ft.app:\n{traceback.format_exc()}")
        print(f"\n[FATAL] Error al iniciar la aplicacion: {e}", flush=True)
        traceback.print_exc()
        input("\nPresione Enter para salir...")

