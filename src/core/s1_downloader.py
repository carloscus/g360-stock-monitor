from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import requests

from src.core.constants import S1_URL
from src.core.xls_fallback import leer_xls_fallback

logger = logging.getLogger(__name__)


def _infer_ext(resp: requests.Response) -> str:
    ct = (resp.headers.get("content-type") or "").lower()
    if "spreadsheetml" in ct or "openxmlformats" in ct:
        return ".xlsx"
    if "excel" in ct:
        return ".xls"
    cd = resp.headers.get("content-disposition") or ""
    if ".xlsx" in cd:
        return ".xlsx"
    if ".xls" in cd:
        return ".xls"
    return ".xls"


def download_source1() -> dict[str, dict[str, dict]] | None:
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(S1_URL, headers=headers, timeout=120)
        resp.raise_for_status()

        suffix = _infer_ext(resp)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(resp.content)
            tmp_path = tmp.name

        try:
            return _parse_source1(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    except Exception as ex:
        print(f"[S1 Downloader] Error: {ex}")
        return None


_HEADER_KEYWORDS = {
    "sku": ["CÓDIGO", "CODIGO", "SKU", "COD.", "ITEM"],
    "descripcion": ["ARTÍCULO", "DESCRIPCIÓN", "DESCRIPCION", "PRODUCTO", "NOMBRE"],
    "almacen": ["ALMACÉN", "ALMACEN", "DEPÓSITO", "DEPOSITO", "UBICACIÓN"],
    "sku_unit": ["U.M.", "UM", "UNIDAD", "UNID", "UOM"],
    "stock": ["STOCK", "SALDO", "CANTIDAD"],
    "predespacho": ["PREDESPACHO", "PRE-DESPACHO", "PREDESP"],
    "disponible": ["DISPONIBLE", "DISP.", "SALDO DISPONIBLE"],
}

_FALLBACK_COL_MAP = {
    "sku": 1, "descripcion": 2, "almacen": 9,
    "sku_unit": 12, "stock": 13, "predespacho": 16, "disponible": 18,
}


def _detect_column_map(filas: list[list[str]]) -> tuple[dict[str, int], int, bool]:
    for i, row in enumerate(filas):
        norm = [str(c).strip().upper() for c in row]
        found = {}
        for key, keywords in _HEADER_KEYWORDS.items():
            for kw in keywords:
                try:
                    idx = norm.index(kw)
                    found[key] = idx
                    break
                except ValueError:
                    continue

        if found.get("sku") is not None and found.get("stock") is not None:
            return found, i, True

        # Edge case: S1 Excel has SKU column unnamed (just before ARTÍCULO)
        if "sku" not in found and found.get("descripcion") is not None:
            sku_idx = found["descripcion"] - 1
            if sku_idx >= 0:
                found["sku"] = sku_idx

        if found.get("sku") is not None and found.get("stock") is not None:
            return found, i, True

    return dict(_FALLBACK_COL_MAP), 10, False


def _safe_int(raw: object) -> int:
    try:
        return int(float(str(raw or "0").replace(",", "").strip()))
    except (ValueError, TypeError, AttributeError):
        return 0


def _parse_source1(path: str) -> dict[str, dict[str, dict]]:
    filas = leer_xls_fallback(path)
    if not filas:
        return {}

    col_map, header_row, found_header = _detect_column_map(filas)
    if not found_header:
        logger.warning("Headers S1 no detectados — usando mapeo fijo de columnas")
    max_col = max(col_map.values()) if col_map else 19

    resultado: dict[str, dict[str, dict]] = {}
    last_sku, last_desc = "", ""

    for row in filas[header_row + 1:]:
        if len(row) <= max_col:
            continue

        r_sku = str(row[col_map["sku"]] or "").strip().lstrip("'")
        r_desc = str(row[col_map["descripcion"]] or "").strip()
        r_sku_upper = r_sku.upper()

        if r_sku_upper in ("TOTAL", "SUBTOTAL", "TOTAL GENERAL"):
            last_sku = ""
            continue

        if r_sku and r_sku_upper not in (".", "ARTÍCULO", "ARTICULO"):
            last_sku = r_sku
            last_desc = r_desc

        if not last_sku:
            continue

        almacen_raw = str(row[col_map["almacen"]] or "").strip().upper()
        stock = _safe_int(row[col_map["stock"]])
        pred = _safe_int(row[col_map["predespacho"]])
        disp = _safe_int(row[col_map["disponible"]])
        sku_unit = str(row[col_map["sku_unit"]] or "").strip()

        almacen_row = resultado.setdefault(almacen_raw, {})
        if last_sku not in almacen_row:
            almacen_row[last_sku] = {
                "stock": 0,
                "predespacho": 0,
                "disponible": 0,
                "descripcion": last_desc,
                "sku_unit": sku_unit,
            }
        almacen_row[last_sku]["stock"] += stock
        almacen_row[last_sku]["predespacho"] += pred
        almacen_row[last_sku]["disponible"] += disp

    return resultado
