from __future__ import annotations

import json
import time
import traceback
from datetime import datetime
from pathlib import Path

import flet as ft

from src.config.theme import get_colors, load_theme_preference, save_theme_preference
from src.core.constants import (
    AUTO_REFRESH_INTERVAL,
    CACHE_FILE,
    S1_API_KEY,
    VERSION_CACHE_FILE,
    VERSION_CHECK_INTERVAL,
    VERSION_CHECK_URL,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_MIN_WIDTH,
    WINDOW_MIN_HEIGHT,
    get_local_version,
)
from src.ui.dashboard import Dashboard


_LOG = Path(__file__).resolve().parent.parent / "run_log.txt"


def _log(msg: str):
    with open(_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{__import__('datetime').datetime.now():%H:%M:%S}] {msg}\n")


def _load_cache() -> tuple[dict, str | None]:
    """Carga el cache persistente de stock. Retorna (raw_data, timestamp_iso)."""
    if not CACHE_FILE.exists():
        return {}, None
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        raw = data.get("raw_data", {})
        ts = data.get("timestamp")
        if raw:
            return raw, ts
    except Exception:
        pass
    return {}, None


def _save_cache(raw_data: dict[str, dict[str, dict]]):
    """Guarda raw_data completo con timestamp ISO actual."""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "raw_data": raw_data,
            "timestamp": datetime.now().isoformat(),
        }
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception as ex:
        _log(f"_save_cache: ERROR {ex}")


def _load_version_check_cache() -> dict | None:
    if not VERSION_CACHE_FILE.exists():
        return None
    try:
        with open(VERSION_CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        checked_at = datetime.fromisoformat(data.get("checked_at", ""))
        delta = (datetime.now() - checked_at).total_seconds()
        if delta < VERSION_CHECK_INTERVAL:
            return data
    except Exception:
        pass
    return None


def _save_version_check_cache(remote_version: str, url: str, force: bool):
    try:
        VERSION_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "remote_version": remote_version,
            "url": url,
            "force": force,
            "checked_at": datetime.now().isoformat(),
        }
        with open(VERSION_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception as ex:
        _log(f"_save_version_check_cache: ERROR {ex}")


def _compare_versions(local: str, remote: str) -> bool:
    """Retorna True si remote > local."""
    try:
        return tuple(int(x) for x in remote.split(".")) > tuple(int(x) for x in local.split("."))
    except Exception:
        return remote != local


def _check_version() -> dict | None:
    """Consulta el endpoint de versión del API. Retorna dict con remote_version, url, force o None."""
    try:
        import requests
        headers = {"x-api-key": S1_API_KEY, "Accept": "application/json"}
        resp = requests.get(VERSION_CHECK_URL, headers=headers, timeout=(5, 10))
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        remote_version = str(data.get("version", "")).strip()
        url = str(data.get("url", "")).strip()
        force = bool(data.get("force", False))
        if not remote_version:
            return None
        return {
            "remote_version": remote_version,
            "url": url,
            "force": force,
        }
    except Exception as ex:
        _log(f"_check_version: {ex}")
        return None


class StockMonitorApp:
    def __init__(self, page: ft.Page):
        try:
            self.page = page
            self._raw_data: dict[str, dict[str, dict]] = {}
            self._theme_mode = load_theme_preference()
            self._setup_page()
            self.dashboard = Dashboard(page, self._theme_mode)
            if hasattr(self.dashboard, "set_on_theme_toggle"):
                self.dashboard.set_on_theme_toggle(self._toggle_theme)
            self.dashboard.set_on_refresh(self._on_refresh)
            self._cache_timestamp: str | None = None
            self._local_version = get_local_version()
            self._update_info: dict | None = None
            self._last_auto_refresh: float = 0.0
            self._build()
        except Exception:
            _log(f"[FATAL] StockMonitorApp.__init__:\n{traceback.format_exc()}")
            raise

    def _setup_page(self):
        self.page.title = "Stock Monitor - CIPSA"
        self.page.theme_mode = ft.ThemeMode.DARK if self._theme_mode == "dark" else ft.ThemeMode.LIGHT
        self.page.bgcolor = get_colors(self._theme_mode)["background"]
        self.page.padding = 0
        self.page.window_width = WINDOW_WIDTH
        self.page.window_height = WINDOW_HEIGHT
        self.page.window_min_width = WINDOW_MIN_WIDTH
        self.page.window_min_height = WINDOW_MIN_HEIGHT
        try:
            self.page.window_center()
        except AttributeError:
            pass

        fonts_dir = Path(__file__).resolve().parent.parent / "assets" / "fonts"
        self.page.fonts = {
            "Inter": str(fonts_dir / "Inter-Variable.ttf"),
            "JetBrains Mono": str(fonts_dir / "JetBrainsMono-Variable.ttf"),
        }
        self.page.theme = ft.Theme(font_family="Inter")

    def _build(self):
        _log("_build: starting dashboard.build()...")
        view = self.dashboard.build()
        _log("_build: dashboard.build() OK")
        self.page.add(view)
        self.page.update()
        _log("_build: page.add + update OK")
        self.dashboard.register_overlay()
        _log("_build: overlay (FilePickers) registrado")

        cache_path = Path(__file__).resolve().parent.parent / "assets" / "data" / "sample_data.json"
        cache, ts = _load_cache()
        if cache:
            _log(f"_build: loading cached raw_data...")
            self._raw_data = cache
            self._cache_timestamp = ts
            self.dashboard.update_data(cache, cache_timestamp=ts)
            self.page.update()
            _log("_build: cache loaded OK")
        elif cache_path.exists():
            _log("_build: cache empty, loading sample_data.json...")
            with open(cache_path, encoding="utf-8") as f:
                raw = json.load(f)
            self._raw_data = raw
            self.dashboard.update_data(raw)
            self.page.update()
            _log("_build: sample_data loaded OK")
        else:
            _log("_build: neither cache nor sample_data.json found")
            self.dashboard._show_empty_state("Sin datos disponibles")
            self.dashboard._set_empty_state_status("Esperando datos", self.dashboard.c["warning"])

        _log("_build: scheduling _delayed_load...")
        self.page.run_task(self._delayed_load)
        self._start_auto_refresh()
        _log("_build: done")

    def _toggle_theme(self):
        self._theme_mode = "light" if self._theme_mode == "dark" else "dark"
        save_theme_preference(self._theme_mode)
        self.page.theme_mode = ft.ThemeMode.DARK if self._theme_mode == "dark" else ft.ThemeMode.LIGHT
        self.page.bgcolor = get_colors(self._theme_mode)["background"]
        self.dashboard.update_theme(self._theme_mode)
        self.page.update()

    async def _delayed_load(self):
        import asyncio
        await asyncio.sleep(0.5)
        await self._load_data()
        self.page.run_task(self._post_load_version_check)

    async def _post_load_version_check(self):
        import asyncio
        cached = _load_version_check_cache()
        update_info = None
        if cached:
            remote_version = cached.get("remote_version", "")
            if _compare_versions(self._local_version, remote_version):
                update_info = cached
        else:
            result = _check_version()
            if result and _compare_versions(self._local_version, result["remote_version"]):
                update_info = result
                _save_version_check_cache(result["remote_version"], result["url"], result["force"])
        self._update_info = update_info
        if update_info:
            self.dashboard.set_update_available(update_info)
        else:
            self.dashboard.set_update_available(None)

    async def _on_refresh(self):
        if self._update_info:
            _log("Refresh con actualizacion disponible: limpiando caches")
            try:
                CACHE_FILE.unlink(missing_ok=True)
                VERSION_CACHE_FILE.unlink(missing_ok=True)
                self._cache_timestamp = None
            except Exception as ex:
                _log(f"_on_refresh limpieza cache: {ex}")
        await self._load_data(is_manual=True)
        self.page.run_task(self._post_load_version_check)

    def _start_auto_refresh(self):
        try:
            self._auto_refresh_interval_id = self.page.run_interval(
                self._on_auto_refresh_tick,
                60_000,
            )
            _log(f"_start_auto_refresh: intervalo iniciado ({AUTO_REFRESH_INTERVAL}s)")
        except Exception as ex:
            _log(f"_start_auto_refresh: ERROR {ex}")

    def _on_auto_refresh_tick(self):
        try:
            if self._raw_data:
                if time.time() - self._last_auto_refresh < AUTO_REFRESH_INTERVAL:
                    return
            self._last_auto_refresh = time.time()
            _log("_on_auto_refresh_tick: ejecutando auto-refresh")
            self.page.run_task(self._load_data(is_manual=False))
        except Exception as ex:
            _log(f"_on_auto_refresh_tick: ERROR {ex}")

    async def _load_data(self, is_manual=False):
        import time
        _t0 = time.time()
        _log(f"_load_data: start is_manual={is_manual}")
        self.dashboard.set_loading(True, "Descargando datos...")
        if not self._raw_data:
            self.dashboard._show_empty_state("Sin datos disponibles")
            self.dashboard._set_empty_state_status("Verificando conexión...", self.dashboard.c["info"])
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            _log("_load_data: calling _download_s1 in executor...")
            raw = await loop.run_in_executor(None, self._download_s1)
            _log(f"_load_data: _download_s1 returned {type(raw).__name__}")
            if not raw:
                self.dashboard.set_loading(False)
                self.dashboard.status_text.value = "No se obtuvieron datos"
                self.dashboard.status_text.color = "#ef4444"
                self.dashboard._show_snack("Error: No se obtuvieron datos de S1", is_error=True)
                if not self._raw_data:
                    self.dashboard._set_empty_state_status("Sin datos - API no disponible", self.dashboard.c["error"])
                _log("_load_data: no data, showing error")
                return

            self._raw_data = raw
            _save_cache(raw)
            self._cache_timestamp = datetime.now().isoformat()
            self._last_auto_refresh = time.time()
            _log("_load_data: cache saved")
            self.dashboard.update_data(raw, cache_timestamp=self._cache_timestamp)
            self.dashboard._hide_empty_state()
            _log("_load_data: data updated in dashboard")
            if is_manual:
                self.dashboard._show_snack("Stock actualizado correctamente")
        except Exception as ex:
            _log(f"_load_data: EXCEPTION: {traceback.format_exc()}")
            self.dashboard.status_text.value = f"Error: {str(ex)}"
            self.dashboard.status_text.color = "#ef4444"
            self.dashboard._show_snack(f"Fallo en la descarga: {str(ex)}", is_error=True)
            if not self._raw_data:
                self.dashboard._set_empty_state_status("Error de conexión", self.dashboard.c["error"])
        finally:
            elapsed = time.time() - _t0
            _log(f"_load_data: elapsed={elapsed:.1f}s")
            if elapsed < 2:
                self.dashboard.set_loading(True, "Actualizando vista...")
                self.page.update()
                import asyncio
                await asyncio.sleep(2 - elapsed)
            from datetime import datetime
            from src.core.processor import leer_ultima_actualizacion
            ts = leer_ultima_actualizacion() or datetime.now().strftime('%H:%M:%S')
            age = self.dashboard.format_cache_timestamp(self._cache_timestamp) if not is_manual else ""
            self.dashboard._ts_text.value = f"Ultima act. {ts}{age}"
            self.dashboard._ts_text.color = self.dashboard.c["accent"]
            self.dashboard._ts_badge.visible = True
            self.dashboard.status_text.value = "Datos actualizados"
            self.dashboard.status_text.color = self.dashboard.c["accent"]
            self.dashboard.set_loading(False)
            self.page.update()
            _log("_load_data: done")

    def _download_s1(self) -> dict | None:
        try:
            from src.core.s1_downloader import download_source1
            _log("_download_s1: calling download_source1...")
            result = download_source1()
            if result:
                _log(f"_download_s1: API data OK, {len(result)} warehouses")
                return result
            _log("_download_s1: API returned None")
        except ImportError:
            _log("_download_s1: ImportError (s1_downloader)")
            pass
        except Exception as ex:
            _log(f"_download_s1: Exception: {ex}")
            print(f"[S1] Error: {ex}")

        _log("_download_s1: no data available")
        return None


def main(page: ft.Page):
    StockMonitorApp(page)
