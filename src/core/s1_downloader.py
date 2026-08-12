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
                        "reporte_timestamp", "data_timestamp", "ts", "report_ts",
                        "fecha_descarga")


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


def download_source1(force_special: bool = False, tipo_mktd: bool = False) -> dict[str, dict[str, dict]] | None:
    """Descarga datos desde S1 con reintentos.

    Args:
        force_special: incluye almacenes s* con include_special=true
        tipo_mktd: filtra por SKUs que tengan al menos un almacén tipo MKTD
    """
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
    if tipo_mktd:
        params["tipo"] = "mktd"

    last_exception = None
    label = "MKTD" if tipo_mktd else ("special" if force_special else "general")
    for attempt in range(3):
        try:
            resp = requests.get(f"{S1_API_URL}/stock", headers=headers, timeout=(30, 120), params=params)
            resp.raise_for_status()
            data = resp.json()

            _API_META.clear()
            _API_META.update(data.get("metadata", {}) or data.get("meta", {}))

            parsed = _parse_source1(data)
            if parsed:
                _log_warehouses(parsed, source=label)
            return parsed

        except Exception as ex:
            last_exception = ex
            print(f"[S1 Downloader] Error intento {attempt+1}/3 ({label}): {ex}")
            if attempt < 2:
                time.sleep(2 ** attempt)

    print(f"[S1 Downloader] Todos los intentos fallaron en {label}. Último error: {last_exception}")
    return None


def download_source1_for_warehouse(warehouse_code: str) -> dict[str, dict] | None:
    """Descarga stock de un almacén específico por código (usado para s*)."""
    headers = {
        "x-api-key": S1_API_KEY,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
    }
    params = {"almacen": warehouse_code}
    for attempt in range(3):
        try:
            resp = requests.get(f"{S1_API_URL}/stock", headers=headers, timeout=(30, 120), params=params)
            resp.raise_for_status()
            data = resp.json()
            parsed = _parse_source1(data)
            if parsed:
                _log_warehouses(parsed, source=f"warehouse:{warehouse_code}")
            return parsed
        except Exception as ex:
            print(f"[S1 Downloader] Error intentando {warehouse_code} intento {attempt+1}/3: {ex}")
            if attempt < 2:
                time.sleep(2 ** attempt)
    return None


def download_almacenes(tipo: str | None = None) -> list[dict]:
    """Descarga la lista de almacenes desde /api/v1/almacenes con filtro opcional por tipo."""
    _UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
    headers = {"x-api-key": S1_API_KEY, "User-Agent": _UA}
    params = {"tipo": tipo} if tipo else {}
    try:
        resp = requests.get(f"{S1_API_URL}/almacenes", headers=headers, timeout=(10, 30), params=params)
        resp.raise_for_status()
        data = resp.json()
        items = data if isinstance(data, list) else data.get("items", data.get("almacenes", []))
        return items
    except Exception as ex:
        print(f"[S1 Downloader] Error en /almacenes: {ex}")
        return []


def _enrich_special_warehouses(parsed: dict[str, dict[str, dict]]):
    """Para almacenes s* detectados, asegura rol informativo y metadatos básicos."""
    for cod in list(parsed.keys()):
        if SPECIAL_WAREHOUSE_RE.match(cod):
            for info in parsed[cod].values():
                info.setdefault("almacen_tipo", "informativo")


def _warehouse_name(cod: str, tipo: str) -> str:
    """Genera nombre legible para almacén cuando la API no provee uno."""
    tipo = (tipo or "").lower().strip()
    if "mktd" in tipo:
        return f"MKTD {cod}"
    if "venta" in tipo:
        if cod == "VES":
            return "Venta Principal"
        return f"Almacén {cod}"
    if cod.startswith("S"):
        return f"MKTD {cod}"
    return f"Almacén {cod}"


def _log_warehouses(parsed: dict[str, dict[str, dict]], source: str = "general"):
    """Log simple de warehouses detectados compatible con el handler de _log."""
    all_codes = list(parsed.keys())
    import re as _re
    specials = [c for c in all_codes if _re.match(r"^(?:s\d+|118|122)$", c, _re.IGNORECASE)]
    print(f"[S1 Downloader] {source}: {len(all_codes)} warehouses: {all_codes} | especiales: {specials or 'ninguno'}")


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
            almacen_raw = str(alm.get("almacen", "")).strip()
            almacen = almacen_raw.upper()
            if not almacen:
                continue

            # Capturar tipo del API (venta/mktd) para clasificación
            alm_tipo = str(alm.get("tipo", "")).lower().strip()
            if SPECIAL_WAREHOUSE_RE.match(almacen_raw):
                if not alm_tipo:
                    alm = dict(alm)
                    alm["tipo"] = "informativo"
                    alm_tipo = "mktd"  # s* son mktd por defecto
                # Nombre del almacén
                alm_nombre = alm.get("nombre") or alm.get("descripcion") or alm.get("label")
                if not alm_nombre or not str(alm_nombre).strip():
                    alm_nombre = _warehouse_name(almacen, alm_tipo)
                alm["nombre_almacen"] = str(alm_nombre).strip()
            else:
                # Para almacenes normales, detectar tipo
                if not alm_tipo:
                    alm_tipo = "venta"  # default

            almacen_row = resultado.setdefault(almacen, {})
            if sku not in almacen_row:
                almacen_row[sku] = {
                    "stock": 0,
                    "predespacho": 0,
                    "disponible": 0,
                    "descripcion": descripcion,
                    "sku_unit": sku_unit,
                    "almacen_tipo": alm_tipo,
                    "almacen_categoria": alm_tipo,  # venta o mktd
                    "nombre_almacen": alm.get("nombre_almacen", f"ALMACEN_{almacen}"),
                }
            almacen_row[sku]["stock"] += int(alm.get("stock", 0) or 0)
            almacen_row[sku]["predespacho"] += int(alm.get("predespacho", 0) or 0)
            almacen_row[sku]["disponible"] += int(alm.get("disponible", 0) or 0)

    return resultado
