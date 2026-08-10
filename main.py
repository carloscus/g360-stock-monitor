from __future__ import annotations

import sys
import traceback
from pathlib import Path

import flet as ft

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.app import StockMonitorApp  # noqa: E402


_LOG_PATH = BASE_DIR / "run_log.txt"


def _log(msg: str):
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{__import__('datetime').datetime.now():%H:%M:%S}] {msg}\n")


def main(page: ft.Page):
    try:
        StockMonitorApp(page)
    except Exception:
        _log(f"[FATAL] Error en StockMonitorApp:\n{traceback.format_exc()}")
        raise


if __name__ == "__main__":
    _log("MAIN_START: __name__ == __main__")
    try:
        _log("PRE: llamando a ft.app(main) desktop...")
        ft.app(main, view=ft.AppView.FLET_APP)
        _log("POST: ft.app(main) retorno OK")
    except Exception as e:
        _log(f"[FATAL] Error en ft.app:\n{traceback.format_exc()}")
        print(f"\n[FATAL] Error al iniciar la aplicacion: {e}", flush=True)
        traceback.print_exc()
        input("\nPresione Enter para salir...")
