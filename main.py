import sys
import flet as ft
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.app import StockMonitorApp  # noqa: E402


def main(page: ft.Page):
    StockMonitorApp(page)


if __name__ == "__main__":
    try:
        ft.run(main)
    except Exception as e:
        print(f"\n[FATAL] Error al iniciar la aplicacion: {e}", flush=True)
        import traceback
        traceback.print_exc()
        input("\nPresione Enter para salir...")
