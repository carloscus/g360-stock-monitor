from __future__ import annotations

import logging

import requests

from src.core.constants import S1_API_KEY, S1_API_URL

logger = logging.getLogger(__name__)

_API_SKU_META: dict[str, dict] = {}


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


def download_source1() -> dict[str, dict[str, dict]] | None:
    try:
        headers = {
            "x-api-key": S1_API_KEY,
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        }
        resp = requests.get(f"{S1_API_URL}/stock", headers=headers, timeout=(15, 60))
        resp.raise_for_status()
        data = resp.json()

        return _parse_source1(data)

    except Exception as ex:
        print(f"[S1 Downloader] Error: {ex}")
        return None


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
