from __future__ import annotations

import hashlib
import json
import threading
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
from src.core.s1_downloader import get_api_sku_meta
from src.ui.dashboard import Dashboard

# Use the shared singleton logger from main.py (set up there first)
import logging
_log_logger = logging.getLogger("g360.stock_monitor")
if not _log_logger.handlers:
    from logging.handlers import RotatingFileHandler
    _log_path = Path(__file__).resolve().parent.parent / "run_log.txt"
    _fmt = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
    _handler = RotatingFileHandler(_log_path, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
    _handler.setFormatter(_fmt)
    _log_logger.addHandler(_handler)
    _log_logger.setLevel(logging.INFO)


def _log(msg: str):
    _log_logger.info(msg)


def _load_cache() -> tuple[dict, str | None, str | None]:
    """Carga el cache persistente. Retorna (raw_data, app_ts, api_ts)."""
    if not CACHE_FILE.exists():
        return {}, None, None
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        raw = data.get("raw_data", {})
        ts = data.get("timestamp")
        api_ts = data.get("api_timestamp")
        if raw:
            return raw, ts, api_ts
    except (json.JSONDecodeError, UnicodeDecodeError) as ex:
        _log(f"_load_cache: corrupt cache file, removing: {ex}")
        try:
            CACHE_FILE.unlink(missing_ok=True)
        except Exception:
            pass
    except Exception:
        pass
    return {}, None, None


def _hash_data(raw_data: dict) -> str:
    """SHA-256 del raw_data para detectar cambios sin descargar dos veces."""
    serialized = json.dumps(raw_data, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(serialized).hexdigest()[:16]


def _data_changed(new_data: dict, last_hash: str | None) -> tuple[bool, str]:
    """Retorna (changed, nuevo_hash)."""
    h = _hash_data(new_data)
    return h != last_hash, h


def _save_cache(raw_data: dict[str, dict[str, dict]], api_timestamp: str | None = None):
    """Guarda raw_data completo. Usa api_timestamp del API como fuente de verdad."""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "raw_data": raw_data,
            "timestamp": api_timestamp or datetime.now().isoformat(),
            "api_timestamp": api_timestamp,
        }
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception as ex:
        _log(f"_save_cache: ERROR {ex}")


def _save_snapshots_before_overwrite():
    """No-op: snapshots se guardan en DATA_DIR/_snapshot_*.json de forma independiente.
    La única acción necesaria es que _save_cache no toque esos archivos."""
    pass


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
            self._api_timestamp: str | None = None
            self._stale_data: bool = False
            self._local_version = get_local_version()
            self._update_info: dict | None = None
            self._last_auto_refresh: float = 0.0
            self._auto_refresh_stop: threading.Event | None = None
            self._download_lock = threading.Lock()
            self._last_data_hash: str | None = None
            self._last_meta_hash: str | None = None
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
        cache, ts, api_ts = _load_cache()
        if cache:
            _log(f"_build: loading cached raw_data...")
            self._raw_data = cache
            self._cache_timestamp = ts
            self._api_timestamp = api_ts
            # Establecer hash inicial para evitar rebuild si la API no cambió
            _, initial_hash = _data_changed(cache, None)
            self._last_data_hash = initial_hash
            self.dashboard.update_data(cache, cache_timestamp=ts, api_timestamp=api_ts)
            self.page.update()
            _log(f"_build: cache loaded OK ({len(cache)} warehouses)")
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
            self._auto_refresh_stop = threading.Event()
            t = threading.Thread(
                target=self._auto_refresh_loop,
                daemon=True,
                name="auto-refresh",
            )
            t.start()
            self._auto_refresh_thread = t
            _log(f"_start_auto_refresh: hilo iniciado ({AUTO_REFRESH_INTERVAL}s)")
        except Exception as ex:
            _log(f"_start_auto_refresh: ERROR {ex}")

    def shutdown(self):
        """Detiene el auto-refresh de forma limpia antes de cerrar."""
        if self._auto_refresh_stop:
            _log("_shutdown: deteniendo auto-refresh...")
            self._auto_refresh_stop.set()
            t = getattr(self, "_auto_refresh_thread", None)
            if t and t.is_alive():
                t.join(timeout=3)
            _log("_shutdown: auto-refresh detenido")

    def _auto_refresh_loop(self):
        while not self._auto_refresh_stop.is_set():
            time.sleep(1)
            try:
                self._on_auto_refresh_tick()
            except Exception as ex:
                _log(f"_auto_refresh_loop: ERROR {ex}")

    def _on_auto_refresh_tick(self):
        try:
            if not self._cache_timestamp:
                return
            self.dashboard._update_refresh_status(
                self._cache_timestamp, self._api_timestamp, self._stale_data
            )
            if time.time() - self._last_auto_refresh < AUTO_REFRESH_INTERVAL:
                return
            self._last_auto_refresh = time.time()
            _log("_on_auto_refresh_tick: ejecutando auto-refresh")
            self.page.run_task(self._load_data, is_manual=False)
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
        if not self._download_lock.acquire(blocking=False):
            _log("_load_data: otra descarga en curso, omitiendo")
            self.dashboard.set_loading(False)
            return
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

            changed, new_hash = _data_changed(raw, self._last_data_hash)
            if not changed:
                # Check if SKU metadata changed (e.g., sin_catalogo, categoria)
                import hashlib
                meta_items = sorted(get_api_sku_meta().items())
                current_meta_hash = hashlib.md5(str(meta_items).encode()).hexdigest()
                if current_meta_hash == self._last_meta_hash:
                    _log("_load_data: datos y metadata identicos, omitiendo UI refresh")
                    self.dashboard.set_loading(False)
                    self._download_lock.release()
                    return
                _log("_load_data: metadata cambio, force rebuild KPIs")

            # Log de almacenes detectados (para debug)
            alm_codes = list(raw.keys())
            import re as _re
            special = [c for c in alm_codes if _re.match(r"^(?:s\d+|118|122)$", c, _re.IGNORECASE)]
            _log(f"_load_data: {len(alm_codes)} warehouses OK, especiales detectados: {special or 'ninguno'}")
            self._raw_data = raw
            self._last_data_hash = new_hash
            _save_cache(raw, self._api_timestamp)
            self._cache_timestamp = datetime.now().isoformat()
            self._last_auto_refresh = time.time()
            _log("_load_data: cache saved")
            self.dashboard.update_data(raw, cache_timestamp=self._cache_timestamp, api_timestamp=self._api_timestamp, stale=self._stale_data)
            self.dashboard._hide_empty_state()
            _log("_load_data: data updated in dashboard")
            if is_manual:
                self.dashboard._show_snack("Stock actualizado correctamente")
        except Exception as ex:
            _log(f"_load_data: EXCEPTION: {traceback.format_exc()}")
            self.dashboard.status_text.value = f"Error: {str(ex)}"
            self.dashboard.status_text.color = "#ef4444"
            self.dashboard._show_snack(f"Fallo en la descarga: {str(ex)}", is_error=True)
            self.dashboard.set_offline(True)
            if not self._raw_data:
                self.dashboard._set_empty_state_status("Error de conexión", self.dashboard.c["error"])
        finally:
            elapsed = time.time() - _t0
            _log(f"_load_data: elapsed={elapsed:.1f}s")
            self._download_lock.release()
            if elapsed < 2:
                self.dashboard.set_loading(True, "Actualizando vista...")
                self.page.update()
                import asyncio
                await asyncio.sleep(2 - elapsed)
            from src.core.processor import leer_ultima_actualizacion
            ts = leer_ultima_actualizacion() or datetime.now().strftime('%H:%M:%S')
            age = self.dashboard.format_cache_timestamp(self._cache_timestamp) if not is_manual else ""
            self.dashboard._ts_text.value = f"Ultima act. {ts}{age}"
            if self._stale_data:
                self.dashboard._ts_text.color = self.dashboard.c["warning"]
                self.dashboard._ts_text.value += " (caché)"
                self.dashboard.status_text.value = "Datos en caché (fuera de horario)"
                self.dashboard.status_text.color = self.dashboard.c["warning"]
                self.dashboard._show_stale_warning()
            else:
                self.dashboard._ts_text.color = self.dashboard.c["accent"]
                self.dashboard.status_text.value = "Datos actualizados"
                self.dashboard.status_text.color = self.dashboard.c["accent"]
                self.dashboard._hide_stale_warning()
            self.dashboard._update_refresh_status(self._cache_timestamp, self._api_timestamp, self._stale_data)
            self.dashboard.set_offline(False)
            self.dashboard.set_loading(False)
            self.page.update()
            _log("_load_data: done")

    def _download_s1(self) -> dict | None:
        from src.core.s1_downloader import download_source1, download_source1_for_warehouse, download_almacenes, get_api_meta, get_api_timestamp, get_api_sku_meta
        from src.core.constants import SPECIAL_WAREHOUSE_RE
        try:
            _log("_download_s1: downloading general stock...")
            result = download_source1()
            if not result:
                _log("_download_s1: general failed, trying MKTD filter...")
                result = download_source1(tipo_mktd=True)
            if result:
                self._stale_data = get_api_meta().get("cache_expirado", False)
                self._api_timestamp = get_api_timestamp()

                # Fallback: si el API no envía timestamp, usar edad del archivo de cache
                if not self._api_timestamp and self._cache_timestamp:
                    try:
                        cache_age_min = (datetime.now() - datetime.fromisoformat(self._cache_timestamp)).total_seconds() / 60
                        if cache_age_min > 180:
                            _log(f"_download_s1: sin api_ts, cache tiene {cache_age_min:.0f} min → marcando stale")
                            self._stale_data = True
                    except Exception:
                        pass

                # Merge S* warehouses from almacenes endpoint + individual downloads
                _merge_special_warehouses(result)

                # Hash: skip si los datos no cambiaron desde la última carga exitosa
                _, changed = _data_changed(result, self._last_data_hash)
                if not changed:
                    # Check if SKU metadata changed (e.g., sin_catalogo, categoria)
                    import hashlib
                    meta_items = sorted(get_api_sku_meta().items())
                    current_meta_hash = hashlib.md5(str(meta_items).encode()).hexdigest()
                    if current_meta_hash != self._last_meta_hash:
                        _log("_download_s1: metadata cambio (sin_catalogo/etc), force rebuild")
                        self._last_meta_hash = current_meta_hash
                    else:
                        _log("_download_s1: datos y metadata identicos, retornando None para skip")
                        return None

                _log(f"_download_s1: API data OK, {len(result)} warehouses, stale={self._stale_data}, api_ts={self._api_timestamp}")
                return result
            self._stale_data = False
            self._api_timestamp = None
            _log("_download_s1: API returned None")
        except ImportError:
            _log("_download_s1: ImportError (s1_downloader)")
            self._stale_data = False
            self._api_timestamp = None
        except Exception as ex:
            _log(f"_download_s1: Exception: {ex}")
            self._stale_data = False
            self._api_timestamp = None
            print(f"[S1] Error: {ex}")

        _log("_download_s1: no data available")
        return None


def _merge_special_warehouses(result: dict[str, dict[str, dict]]) -> None:
    """Agrega almacenes s* faltantes como placeholders cuando la respuesta no los incluye.

    El API trae stock real para los almacenes s* (fuente general/sucursales consolidada).
    Esta funcion solo garantiza que todos los almacenes s* conocidos aparezcan en el UI
    si por algun motivo la respuesta actual no los incluye.
    """
    from src.core.s1_downloader import download_almacenes, _warehouse_name
    from src.core.constants import SPECIAL_WAREHOUSE_RE
    try:
        mktd_almacenes = download_almacenes(tipo="mktd")
        mktd_codes = {str(a.get("codigo", a.get("almacen", ""))).upper() for a in mktd_almacenes if a}
        special_codes = {c for c in mktd_codes if SPECIAL_WAREHOUSE_RE.match(c)}
        missing = special_codes - set(result.keys())
        if not missing:
            return
        _log(f"_merge_special_warehouses: {len(missing)} s* warehouses sin datos en la respuesta: {sorted(missing)}")
        for cod in sorted(missing):
            alm_info = next((a for a in mktd_almacenes if str(a.get("codigo", a.get("almacen", ""))).upper() == cod), None)
            tipo = (alm_info.get("tipo", "") if alm_info else "").lower()
            nombre = _warehouse_name(cod, tipo)
            # Placeholder vacio: el API no trajo stock para este s* en la respuesta actual.
            result[cod] = {}
            _log(f"_merge_special_warehouses: {cod} ({nombre}) agregado como placeholder")
    except Exception as ex:
        _log(f"_merge_special_warehouses: ERROR {ex}")


def main(page: ft.Page):
    StockMonitorApp(page)
