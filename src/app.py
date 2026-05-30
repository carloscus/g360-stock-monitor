from __future__ import annotations

import json
from pathlib import Path

import flet as ft

from src.config.theme import get_colors, load_theme_preference, save_theme_preference
from src.ui.dashboard import Dashboard


class StockMonitorApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self._raw_data: dict[str, dict[str, dict]] = {}
        self._theme_mode = load_theme_preference()
        self._setup_page()
        self.dashboard = Dashboard(page, self._theme_mode)
        # Registrar el callback para cambio de tema si el dashboard lo permite
        if hasattr(self.dashboard, "set_on_theme_toggle"):
            self.dashboard.set_on_theme_toggle(self._toggle_theme)
        self.dashboard.set_on_refresh(self._on_refresh)
        self._build()

    def _setup_page(self):
        self.page.title = "Stock Monitor - CIPSA"
        self.page.theme_mode = ft.ThemeMode.DARK if self._theme_mode == "dark" else ft.ThemeMode.LIGHT
        self.page.bgcolor = get_colors(self._theme_mode)["background"]
        self.page.padding = 0
        self.page.window_width = 1200
        self.page.window_height = 800
        self.page.window_min_width = 900
        self.page.window_min_height = 600
        try:
            self.page.window_center()
        except AttributeError:
            pass

    def _build(self):
        view = self.dashboard.build()
        self.page.add(view)
        self.page.update()
        self.page.run_task(self._delayed_load)

    def _toggle_theme(self):
        self._theme_mode = "light" if self._theme_mode == "dark" else "dark"
        save_theme_preference(self._theme_mode)
        
        self.page.theme_mode = ft.ThemeMode.DARK if self._theme_mode == "dark" else ft.ThemeMode.LIGHT
        self.page.bgcolor = get_colors(self._theme_mode)["background"]
        
        # Notificar al dashboard para que actualice colores internos
        self.dashboard.update_theme(self._theme_mode)
        self.page.update()

    async def _delayed_load(self):
        import asyncio
        await asyncio.sleep(0.5)
        await self._load_data()

    async def _on_refresh(self):
        await self._load_data(is_manual=True)

    async def _load_data(self, is_manual=False):
        import time
        _t0 = time.time()
        self.dashboard.set_loading(True, "Descargando datos...")
        try:
            raw = self._download_s1()
            if not raw:
                self.dashboard.set_loading(False)
                self.dashboard.status_text.value = "No se obtuvieron datos"
                self.dashboard.status_text.color = "#ef4444"
                self.page.update()
                self.dashboard._show_snack("Error: No se obtuvieron datos de S1", is_error=True)
                return

            self._raw_data = raw
            self.dashboard.update_data(raw)
            if is_manual:
                self.dashboard._show_snack("Stock actualizado correctamente")
        except Exception as ex:
            self.dashboard.status_text.value = f"Error: {str(ex)}"
            self.dashboard.status_text.color = "#ef4444"
            self.dashboard._show_snack(f"Fallo en la descarga: {str(ex)}", is_error=True)
        finally:
            elapsed = time.time() - _t0
            if elapsed < 2:
                import asyncio
                self.dashboard.set_loading(True, "Actualizando vista...")
                self.page.update()
                await asyncio.sleep(2 - elapsed)
            from datetime import datetime
            ts = datetime.now().strftime('%H:%M:%S')
            self.dashboard._ts_text.value = f"Última act. {ts}"
            self.dashboard._ts_text.color = self.dashboard.c["accent"]
            self.dashboard._ts_badge.visible = True
            self.dashboard.status_text.value = "Datos actualizados"
            self.dashboard.status_text.color = self.dashboard.c["accent"]
            self.dashboard.set_loading(False)
            self.page.update()

    def _download_s1(self) -> dict | None:
        try:
            from src.core.s1_downloader import download_source1
            result = download_source1()
            return result
        except ImportError:
            pass
        except Exception as ex:
            print(f"[S1] Error: {ex}")
            return None

        sample_path = Path(__file__).resolve().parent.parent / "assets" / "data" / "sample_data.json"
        if sample_path.exists():
            with open(sample_path, encoding="utf-8") as f:
                return json.load(f)

        return None


def main(page: ft.Page):
    StockMonitorApp(page)
