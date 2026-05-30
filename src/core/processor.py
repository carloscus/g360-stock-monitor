from __future__ import annotations

import json
import os
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment

from src.core.constants import LINEAS_FILE, DATA_DIR


_CATALOGO: list[dict] | None = None


def _load_catalogo() -> list[dict]:
    global _CATALOGO
    if _CATALOGO is not None:
        return _CATALOGO
    path = DATA_DIR / "catalogo_productos.json"
    if not path.exists():
        _CATALOGO = []
        return _CATALOGO
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    _CATALOGO = data.get("productos", [])
    return _CATALOGO

def reload_catalogo():
    """Limpia la caché del catálogo para forzar una recarga desde disco."""
    global _CATALOGO
    _CATALOGO = None
    _load_catalogo()

def update_catalogo_sku(sku: str, descripcion: str = "", linea: str = "", categoria: str = ""):
    """Agrega o actualiza un SKU en catalogo_productos.json y recarga la caché."""
    global _CATALOGO
    path = DATA_DIR / "catalogo_productos.json"
    data = {"productos": []}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    productos = data.get("productos", [])
    found = None
    for p in productos:
        if p["sku"] == sku:
            found = p
            break
    if found:
        if linea:
            found["linea"] = linea
        if categoria:
            found["categoria"] = categoria
        if descripcion:
            found["descripcion"] = descripcion
    else:
        entry = {"sku": sku, "orden": 9999, "un_bx": 1}
        if linea:
            entry["linea"] = linea
        if categoria:
            entry["categoria"] = categoria
        if descripcion:
            entry["descripcion"] = descripcion
        productos.append(entry)
    data["productos"] = productos
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _CATALOGO = None
    _load_catalogo()

def _sku_info(sku: str) -> dict:
    for p in _load_catalogo():
        if p["sku"] == sku:
            return {
                "linea": p.get("linea", ""),
                "categoria": p.get("categoria", ""),
                "un_bx": p.get("un_bx", 1),
                "indice": p.get("orden", 9999),
            }
    return {"linea": "SIN LINEA", "categoria": "OTROS", "un_bx": 1, "indice": 9999}


def load_lineas() -> dict:
    with open(LINEAS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _warehouse_disp(warehouse_data: dict[str, dict], sku: str) -> int:
    info = warehouse_data.get(sku)
    if not info:
        return 0
    return info.get("disponible", max(0, info.get("stock", 0) - info.get("predespacho", 0)))


def calcular_kpis_almacen(
    raw: dict[str, dict[str, dict]]
) -> dict[str, dict]:
    result = {}
    for cod_alm, skus in raw.items():
        lineas_kpi: dict[str, dict] = {}
        categorias_kpi: dict[str, dict] = {}
        stock_total = 0
        predespacho_total = 0
        disponible_total = 0
        bx_total = 0
        disp_bx = 0
        alertas = 0
        criticos = 0
        sobre_comprometidos = 0
        sku_count = 0

        for sku, info in skus.items():
            stock = info.get("stock", 0)
            pred = info.get("predespacho", 0)
            disp = info.get("disponible", max(0, stock - pred))

            stock_total += stock
            predespacho_total += pred
            disponible_total += disp
            sku_count += 1

            un_bx = _sku_info(sku)["un_bx"]
            bx_total += stock // un_bx if un_bx > 0 else stock
            disp_bx += disp // un_bx if un_bx > 0 else disp

            if un_bx > 0 and disp < un_bx:
                criticos += 1
            elif un_bx > 0 and disp <= un_bx * 5:
                alertas += 1

            if stock > 0 and pred / stock >= 0.85:
                sobre_comprometidos += 1

            cat_info = _sku_info(sku)
            linea_cod = cat_info["linea"]
            categoria = cat_info["categoria"]

            if linea_cod:
                if linea_cod not in lineas_kpi:
                    lineas_kpi[linea_cod] = {"skus": 0, "stock": 0, "predespacho": 0, "disponible": 0, "sobre_comprometidos": 0}
                lineas_kpi[linea_cod]["skus"] += 1
                lineas_kpi[linea_cod]["stock"] += stock
                lineas_kpi[linea_cod]["predespacho"] += pred
                lineas_kpi[linea_cod]["disponible"] += disp
                if stock > 0 and pred / stock >= 0.95:
                    lineas_kpi[linea_cod]["sobre_comprometidos"] += 1

            if categoria:
                if categoria not in categorias_kpi:
                    categorias_kpi[categoria] = {"skus": 0, "stock": 0, "predespacho": 0, "disponible": 0}
                categorias_kpi[categoria]["skus"] += 1
                categorias_kpi[categoria]["stock"] += stock
                categorias_kpi[categoria]["predespacho"] += pred
                categorias_kpi[categoria]["disponible"] += disp

        prev = _load_snapshot(cod_alm)
        cambio = None
        if prev and prev.get("disponible_total") is not None:
            diff = disponible_total - prev["disponible_total"]
            pct = (diff / prev["disponible_total"] * 100) if prev["disponible_total"] > 0 else 0
            cambio = {"absoluto": diff, "porcentaje": round(pct, 1)}

        result[cod_alm] = {
            "codigo": cod_alm,
            "stock_total": stock_total,
            "predespacho_total": predespacho_total,
            "disponible_total": disponible_total,
            "bx_total": bx_total,
            "disponible_bx": disp_bx,
            "sku_count": sku_count,
            "alertas": alertas,
            "criticos": criticos,
            "sobre_comprometidos": sobre_comprometidos,
            "lineas": lineas_kpi,
            "categorias": categorias_kpi,
            "cambio": cambio,
            "ultima_actualizacion": datetime.now().strftime("%H:%M"),
        }
        _save_snapshot(cod_alm, {"disponible_total": disponible_total, "timestamp": datetime.now().isoformat()})

    return result


def obtener_metricas_lineas(
    kpis_por_almacen: dict[str, dict],
    alm_config: dict | None = None,
) -> list[dict]:
    config = load_lineas()
    lineas_config = {ln["codigo"]: ln for ln in config.get("lineas", [])}
    linea_categoria: dict[str, str] = {}
    for p in _load_catalogo():
        lc = p.get("linea", "")
        cat = p.get("categoria", "")
        if lc and cat in PRIMARY_CATEGORIES:
            linea_categoria[lc] = cat
    lineas_aggregated: dict[str, dict] = {}

    for alm_data in kpis_por_almacen.values():
        cod_alm = alm_data.get("codigo", "")
        cfg_alm = alm_config.get(cod_alm, {}) if alm_config else {}
        rol = cfg_alm.get("rol", "")

        for cod_linea, info in alm_data.get("lineas", {}).items():
            if linea_categoria.get(cod_linea) not in PRIMARY_CATEGORIES:
                continue
            if cod_linea not in lineas_aggregated:
                cfg = lineas_config.get(cod_linea, {})
                lineas_aggregated[cod_linea] = {
                    "codigo": cod_linea,
                    "nombre": cfg.get("nombre", cod_linea),
                    "categoria": linea_categoria.get(cod_linea, ""),
                    "grupo": cfg.get("grupo", ""),
                    "stock_minimo": cfg.get("stock_minimo", 0),
                    "stock": 0,
                    "predespacho": 0,
                    "disponible": 0,
                    "skus": 0,
                    "sobre_comprometidos": 0,
                    "stock_ves": 0,
                    "stock_qc": 0,
                    "stock_secundario": 0,
                    "stock_externo": 0,
                    "predespacho_ves": 0,
                }
            entry = lineas_aggregated[cod_linea]
            entry["stock"] += info["stock"]
            entry["predespacho"] += info["predespacho"]
            entry["disponible"] += info["disponible"]
            entry["skus"] += info["skus"]
            entry["sobre_comprometidos"] += info.get("sobre_comprometidos", 0)

            if rol == "PRINCIPAL":
                entry["stock_ves"] += info["stock"]
                entry["predespacho_ves"] += info["predespacho"]
            elif cod_alm == "121":
                entry["stock_qc"] += info["stock"]
            elif rol == "SECUNDARIO":
                entry["stock_secundario"] += info["stock"]
            elif rol == "EXTERNO":
                entry["stock_externo"] += info["stock"]

    for entry in lineas_aggregated.values():
        sm = entry["stock_minimo"]
        sv = entry["stock_ves"]
        if sm > 0 and sv < sm:
            entry["salud"] = "critico"
            entry["pct_minimo"] = round(sv / sm * 100, 1)
        elif sm > 0 and sv < sm * 2:
            entry["salud"] = "alerta"
            entry["pct_minimo"] = round(sv / sm * 100, 1)
        else:
            entry["salud"] = "bueno"
            entry["pct_minimo"] = round(sv / sm * 100, 1) if sm > 0 else 100

    return sorted(
        lineas_aggregated.values(),
        key=lambda x: x["disponible"],
        reverse=True,
    )


PRIMARY_CATEGORIES = {"VINIBALL", "VINIFAN", "REPRESENTADAS"}


def obtener_metricas_categorias(
    kpis_por_almacen: dict[str, dict]
) -> list[dict]:
    categorias: dict[str, dict] = {}
    for alm_data in kpis_por_almacen.values():
        for cat, info in alm_data.get("categorias", {}).items():
            if cat not in PRIMARY_CATEGORIES:
                continue
            if cat not in categorias:
                categorias[cat] = {"categoria": cat, "stock": 0, "predespacho": 0, "disponible": 0, "skus": 0}
            categorias[cat]["stock"] += info["stock"]
            categorias[cat]["predespacho"] += info["predespacho"]
            categorias[cat]["disponible"] += info["disponible"]
            categorias[cat]["skus"] += info["skus"]

    orden = {"VINIBALL": 0, "VINIFAN": 1, "REPRESENTADAS": 2}
    return sorted(
        categorias.values(),
        key=lambda x: orden.get(x["categoria"], 99),
    )


def contar_sin_linea(raw: dict[str, dict[str, dict]]) -> int:
    total = 0
    for skus in raw.values():
        for sku in skus:
            if _sku_info(sku)["categoria"] == "OTROS":
                total += 1
    return total


def _snapshot_path(warehouse_code: str) -> str:
    return str(DATA_DIR / f"_snapshot_{warehouse_code}.json")


def _load_snapshot(warehouse_code: str) -> dict | None:
    path = _snapshot_path(warehouse_code)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def _save_snapshot(warehouse_code: str, data: dict):
    path = _snapshot_path(warehouse_code)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def _warehouse_sort_key(cod: str, alm_config: dict) -> tuple:
    cfg = alm_config.get(cod, {})
    rol = cfg.get("rol", "")
    rol_order = {"PRINCIPAL": 0, "SECUNDARIO": 1, "EXTERNO": 2}
    return (rol_order.get(rol, 9), cfg.get("prioridad", 99))


def sugerir_transferencias(
    raw: dict[str, dict[str, dict]],
    alm_config: dict,
    umbral: int = 5,
    search: str = ""
) -> list[dict]:
    principal = None
    secundarios = []
    for cod, cfg in alm_config.items():
        rol = cfg.get("rol", "")
        if rol == "PRINCIPAL":
            principal = cod
        elif rol == "SECUNDARIO":
            secundarios.append(cod)

    if search:
        resultados = []
        seen_skus = set()
        for cod_alm, skus in raw.items():
            for sku, info in skus.items():
                desc = (info.get("descripcion", "") or "").lower()
                if search not in sku.lower() and search not in desc:
                    continue
                if sku in seen_skus:
                    continue
                seen_skus.add(sku)
                for a in sorted(raw.keys(), key=lambda c: _warehouse_sort_key(c, alm_config)):
                    d = raw[a].get(sku)
                    if not d:
                        continue
                    disp = d.get("disponible", max(0, d.get("stock", 0) - d.get("predespacho", 0)))
                    cat = _sku_info(sku)
                    rol = alm_config.get(a, {}).get("rol", "")
                    resultados.append({
                        "sku": sku,
                        "descripcion": d.get("descripcion", ""),
                        "linea": cat["linea"],
                        "un_bx": cat["un_bx"],
                        "almacen": a,
                        "rol": rol,
                        "stock": d.get("stock", 0),
                        "predespacho": d.get("predespacho", 0),
                        "disponible": disp,
                    })
        return resultados[:20]

    if not principal:
        return []
    p_data = raw.get(principal, {})
    resultados = []

    def add(sku, pinfo, p_disp, scod, sdata, s_disp, tipo):
        cat = _sku_info(sku)
        resultados.append({
            "sku": sku,
            "descripcion": pinfo.get("descripcion", ""),
            "linea": cat["linea"],
            "un_bx": cat["un_bx"],
            "tipo": tipo,
            "principal": principal,
            "p_stock": pinfo.get("stock", 0),
            "p_pred": pinfo.get("predespacho", 0),
            "p_disp": p_disp,
            "secundario": scod,
            "s_stock": sdata.get("stock", 0),
            "s_pred": sdata.get("predespacho", 0),
            "s_disp": s_disp,
        })

    for sku, pinfo in p_data.items():
        p_stock = pinfo.get("stock", 0)
        p_pred = pinfo.get("predespacho", 0)
        p_disp = pinfo.get("disponible", max(0, p_stock - p_pred))

        for scod in sorted(secundarios, key=lambda c: _warehouse_sort_key(c, alm_config)):
            sdata = raw.get(scod, {}).get(sku)
            if not sdata:
                continue
            s_stock = sdata.get("stock", 0)
            s_pred = sdata.get("predespacho", 0)
            s_disp = sdata.get("disponible", max(0, s_stock - s_pred))

            if p_disp <= umbral and s_disp > 0:
                add(sku, pinfo, p_disp, scod, sdata, s_disp, "critico")
                break

            if s_stock > 0 and p_stock > 0 and (s_stock / p_stock) >= 3 and p_disp > umbral:
                add(sku, pinfo, p_disp, scod, sdata, s_disp, "desbalance")
                break

    return resultados

def export_to_excel(data_items: list, file_path: str, title: str, include_details: bool = False, include_summary: bool = True):
    """
    Genera un archivo Excel profesional con hojas por línea y formato condicional.
    """
    wb = Workbook()
    
    if include_summary:
        ws_resumen = wb.active
        ws_resumen.title = "Resumen"
    else:
        ws_resumen = None

    # Agrupar por línea
    grouped_data = {}
    for item in data_items:
        # Extraer info según el formato del diálogo
        sku = item[0] if isinstance(item, (list, tuple)) else item.get("sku")
        info = _sku_info(sku)
        linea = info.get("linea", "SIN LINEA")
        if linea not in grouped_data:
            grouped_data[linea] = []
        grouped_data[linea].append(item)

    # Estilos
    header_fill = PatternFill(start_color="10B981", end_color="10B981", fill_type="solid")
    white_font = Font(color="FFFFFF", bold=True)
    red_fill = PatternFill(start_color="FCA5A5", end_color="FCA5A5", fill_type="solid")
    yellow_fill = PatternFill(start_color="FDE68A", end_color="FDE68A", fill_type="solid")
    green_fill = PatternFill(start_color="BBF7D0", end_color="BBF7D0", fill_type="solid")
    
    if ws_resumen:
        # Configurar Encabezados de Resumen
        resumen_headers = ["Línea", "SKUs", "Stock Total", "Predespacho", "Disponible", "% Predespacho"]
        ws_resumen.append(resumen_headers)
        for cell in ws_resumen[1]:
            cell.fill = header_fill
            cell.font = white_font
            cell.alignment = Alignment(horizontal="center")

    summary_stats = []

    # Ordenar líneas según el catálogo si es posible
    # Usamos el índice del primer producto de cada línea como criterio de orden de la hoja
    def get_line_order(line_name):
        items = grouped_data[line_name]
        if not items:
            return 9999
        return _sku_info(items[0][0] if isinstance(items[0], (tuple, list)) else items[0].get("sku"))["indice"]

    if not grouped_data:
        # Si no hay datos, crear al menos una hoja vacía para evitar error de openpyxl
        wb.create_sheet("Sin Datos")

    sorted_lineas = sorted(grouped_data.keys(), key=get_line_order)

    for linea in sorted_lineas:
        ws = wb.create_sheet(title=linea[:30]) # Excel limita a 31 caracteres
        
        # Encabezados
        headers = ["SKU", "Descripción", "Und", "Disponible (UND)", "Disponible (BX)"]
        if include_details:
            headers.extend(["Stock Total", "Predespacho"])
        
        ws.append(headers)
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = white_font
            cell.alignment = Alignment(horizontal="center")

        # Datos ordenados por índice de catálogo
        items = grouped_data[linea]
        # Intentar ordenar por el campo 'indice' o similar presente en el item
        try:
            items.sort(key=lambda x: _sku_info(x[0] if isinstance(x, (tuple, list)) else x.get("sku"))["indice"])
        except Exception:
            pass

        line_stock = 0
        line_pred = 0
        line_disp = 0

        for d in items:
            # Mapeo genérico de datos según el origen (Warehouse vs Linea vs Criticos)
            if isinstance(d, (list, tuple)) and len(d) >= 6: # Formato Linea/Warehouse
                sku, desc, unit, st, pre, disp = d[0], d[1], d[2], d[3], d[4], d[5]
            else: # Fallback o formatos cortos
                sku = d[0] if isinstance(d, (list, tuple)) else d.get("sku", "")
                info = _sku_info(sku)
                desc = d[1] if isinstance(d, (list, tuple)) else d.get("descripcion", "")
                unit = info.get("sku_unit", "UND")
                disp = d[3] if isinstance(d, (list, tuple)) and len(d) == 4 else (d[5] if isinstance(d, (list, tuple)) else 0)
                st, pre = 0, 0

            line_stock += st
            line_pred += pre
            line_disp += disp

            un_bx = _sku_info(sku)["un_bx"]
            dbx = disp // un_bx if un_bx > 0 else disp
            
            row_data = [sku, desc, unit, disp, dbx]
            if include_details:
                row_data.extend([st, pre])
            
            ws.append(row_data)
            
            # Formato Condicional en columna Disponible (Columna D / Index 4)
            disp_cell = ws.cell(row=ws.max_row, column=4)
            if disp <= 5:
                disp_cell.fill = red_fill
            elif disp <= 10:
                disp_cell.fill = yellow_fill
            else:
                disp_cell.fill = green_fill

        # Ajustar anchos
        ws.column_dimensions['A'].width = 15
        ws.column_dimensions['B'].width = 50
        ws.column_dimensions['D'].width = 15

        # Agregar al listado de resumen
        ratio = (line_pred / line_stock * 100) if line_stock > 0 else 0
        summary_stats.append([linea, len(items), line_stock, line_pred, line_disp, f"{ratio:.1f}%"])

    if ws_resumen:
        # Llenar Hoja de Resumen con los totales calculados
        for row in summary_stats:
            ws_resumen.append(row)
            # Formato condicional básico para disponibilidad en resumen
            disp_val = row[4]
            cell_disp = ws_resumen.cell(row=ws_resumen.max_row, column=5)
            if disp_val <= 50: # Umbral mayor por ser consolidado
                cell_disp.fill = red_fill
            elif disp_val <= 200:
                cell_disp.fill = yellow_fill
            else:
                cell_disp.fill = green_fill
                
            # Alineación
            for i in range(2, 7):
                ws_resumen.cell(row=ws_resumen.max_row, column=i).alignment = Alignment(horizontal="right")

        # Ajustar anchos en Resumen
        ws_resumen.column_dimensions['A'].width = 30
        ws_resumen.column_dimensions['C'].width = 15
        ws_resumen.column_dimensions['D'].width = 15
        ws_resumen.column_dimensions['E'].width = 15
        ws_resumen.column_dimensions['F'].width = 15
    else:
        # Si no hubo resumen, la primera hoja creada (la primera línea) es la activa
        if wb.sheetnames:
            wb.active = 0

    wb.save(file_path)
