from __future__ import annotations

import logging
import re
import time

import requests

from src.core.constants import S1_API_KEY, S1_API_URL, SPECIAL_WAREHOUSE_RE

logger = logging.getLogger(__name__)

_API_SKU_META: dict[str, dict] = {}
_API_META: dict = {}


def get_api_meta() -> dict:
    return _API_META


API_TIMESTAMP_KEYS = ("timestamp", "generated_at", "fecha_actualizacion",
                       "report_timestamp", "updated_at", "last_updated", "created_at",
                       "ultima_actualizacion", "actualizado", "fecha", "hora",
                       "refreshed_at", "last_refresh", "generation_time",
                       "reporte_timestamp", "data_timestamp", "ts", "report_ts")


def get_api_timestamp() -> str | None:
    """Hora en que el API generó el reporte (no cuando lo descargó la app)."""
    for key in API_TIMESTAMP_KEYS:
        val = _API_META.get(key)
        if val:
            return str(val)
    if _API_META:
        import logging
        _meta_keys = list(_API_META.keys())
        logging.warning("s1_downloader: no timestamp found in metadata. Has: %s", _meta_keys)
    return None


def get_api_sku_meta() -> dict[str, dict]:
    """Metadata de catálogo capturada del API (categoria, linea, linea_id, grupo, tipo, familia, estado_linea, un_bx, peso_kg, precio_lista, nombre_corto, ean13, ean14, keywords, sin_catalogo, orden)."""
    return _API_SKU_META


def _normalize_linea(linea: str) -> tuple[str, str]:
    """Convierte '0101 - PELOTAS' en (codigo='PELOTAS', nombre='PELOTAS')."""
    linea = (linea or "").strip()
    if not linea:
        return "", ""
    if " - " in linea:
        codigo = linea.split(" - ", 1)[1].strip()
        return codigo, codigo
    return linea, linea


def download_source1(force_special: bool = False) -> dict[str, dict[str, dict]] | None:
    """Descarga datos desde S1 con reintentos para despertar Render si está dormido."""
    headers = {
        "x-api-key": S1_API_KEY,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
    }
    params = {}
    if force_special:
        params["include_special"] = "true"

    last_exception = None
    for attempt in range(3):
        try:
            resp = requests.get(f"{S1_API_URL}/stock", headers=headers, timeout=(15, 60), params=params)
            resp.raise_for_status()
            data = resp.json()

            _API_META.clear()
            _API_META.update(data.get("metadata", {}) or data.get("meta", {}))

            parsed = _parse_source1(data)
            if parsed:
                _enrich_special_warehouses(parsed)
            return parsed

        except Exception as ex:
            last_exception = ex
            print(f"[S1 Downloader] Error intento {attempt+1}/3: {ex}")
            if attempt < 2:
                time.sleep(2 ** attempt)

    print(f"[S1 Downloader] Todos los intentos fallaron. Último error: {last_exception}")
    return None


def _enrich_special_warehouses(parsed: dict[str, dict[str, dict]]):
    """Para almacenes s* detectados, asegura rol informativo y metadatos básicos."""
    for cod in list(parsed.keys()):
        if SPECIAL_WAREHOUSE_RE.match(cod):
            for info in parsed[cod].values():
                info.setdefault("almacen_tipo", "informativo")


def _parse_source1(data: dict) -> dict[str, dict[str, dict]]:
    items = data.get("items", [])
    resultado: dict[str, dict[str, dict]] = {}

    for item in items:
        sku = str(item.get("sku", "")).strip().lstrip("'")
        if not sku:
            continue

        descripcion = str(item.get("descripcion", "")).strip()
        sku_unit = str(item.get("um", "")).strip()
        linea_cod, linea_nombre = _normalize_linea(str(item.get("linea", "")))
        categoria = str(item.get("categoria", "")).strip()

        _API_SKU_META[sku] = {
            "linea": linea_cod,
            "linea_nombre": linea_nombre,
            "linea_id": str(item.get("linea_id", "")).strip(),
            "categoria": categoria,
            "grupo": str(item.get("grupo", "")).strip(),
            "tipo": str(item.get("tipo", "")).strip(),
            "familia": str(item.get("familia", "")).strip(),
            "estado_linea": str(item.get("estado_linea", "")).strip(),
            "un_bx": int(item.get("un_bx") or item.get("cantidad_por_caja") or 1),
            "peso_kg": float(item.get("peso_kg") or 0),
            "precio_lista": float(item.get("precio") or item.get("precio_lista") or 0),
            "nombre_corto": str(item.get("nombre_corto", "")).strip(),
            "ean13": str(item.get("ean13", "")).strip(),
            "ean14": str(item.get("ean14", "")).strip(),
            "keywords": [str(k).strip() for k in item.get("keywords", []) if str(k).strip()],
            "sin_catalogo": bool(item.get("sin_catalogo")),
            "orden": int(item.get("orden") or 9999),
        }

        for alm in item.get("almacenes", []):
            almacen = str(alm.get("almacen", "")).strip().upper()
            if not almacen:
                continue

            if SPECIAL_WAREHOUSE_RE.match(almacen):
                tipo = alm.get("tipo", "")
                if not tipo:
                    alm = dict(alm)
                    alm["tipo"] = "informativo"

            almacen_row = resultado.setdefault(almacen, {})
            if sku not in almacen_row:
                almacen_row[sku] = {
                    "stock": 0,
                    "predespacho": 0,
                    "disponible": 0,
                    "descripcion": descripcion,
                    "sku_unit": sku_unit,
                    "almacen_tipo": str(alm.get("tipo", "")).strip().lower(),
                }
            almacen_row[sku]["stock"] += int(alm.get("stock", 0) or 0)
            almacen_row[sku]["predespacho"] += int(alm.get("predespacho", 0) or 0)
            almacen_row[sku]["disponible"] += int(alm.get("disponible", 0) or 0)

    return resultado
