from __future__ import annotations

import csv
import io
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional


def leer_xls_fallback(path: str) -> Optional[list[list[str]]]:
    path_obj = Path(path)
    if not path_obj.exists():
        return None

    raw = path_obj.read_bytes()

    engines = [
        ("openpyxl", lambda: _leer_openpyxl(raw)),
        ("xlrd", lambda: _leer_xlrd(raw)),
        ("csv", lambda: _leer_csv(raw)),
        ("html", lambda: _leer_html(raw)),
        ("xml_spreadsheet", lambda: _leer_xml_spreadsheet(raw)),
    ]

    ultimo_error = None
    for nombre, fn in engines:
        try:
            resultado = fn()
            if resultado and len(resultado) > 1:
                return resultado
        except Exception as e:
            ultimo_error = e
            continue

    raise RuntimeError(
        f"No se pudo leer el archivo: {path}. "
        f"Ultimo error: {ultimo_error}"
    )


def _leer_openpyxl(raw: bytes) -> Optional[list[list[str]]]:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    ws = wb.active
    filas = []
    for row in ws.iter_rows(values_only=True):
        filas.append([str(c).strip() if c is not None else "" for c in row])
    wb.close()
    return filas


def _leer_xlrd(raw: bytes) -> Optional[list[list[str]]]:
    import xlrd
    wb = xlrd.open_workbook(file_contents=raw)
    ws = wb.sheet_by_index(0)
    filas = []
    for row_idx in range(ws.nrows):
        filas.append([str(ws.cell_value(row_idx, c)).strip() for c in range(ws.ncols)])
    return filas


def _leer_csv(raw: bytes) -> Optional[list[list[str]]]:
    content = raw.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(content))
    return [row for row in reader]


def _leer_html(raw: bytes) -> Optional[list[list[str]]]:
    from bs4 import BeautifulSoup
    content = raw.decode("utf-8", errors="replace")
    soup = BeautifulSoup(content, "html.parser")
    table = soup.find("table")
    if not table:
        return None
    filas = []
    for tr in table.find_all("tr"):
        celdas = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if celdas:
            filas.append(celdas)
    return filas


def _leer_xml_spreadsheet(raw: bytes) -> Optional[list[list[str]]]:
    NS = {
        "ss": "urn:schemas-microsoft-com:office:spreadsheet",
        "o": "urn:schemas-microsoft-com:office:office",
        "x": "urn:schemas-microsoft-com:office:excel",
    }
    root = ET.fromstring(raw)
    worksheet = root.find(".//ss:Worksheet", NS)
    if worksheet is None:
        worksheet = root.find(".//Worksheet")
    if worksheet is None:
        return None

    table = worksheet.find(".//ss:Table", NS) or worksheet.find(".//Table")
    if table is None:
        return None

    filas = []
    for row in table.findall(".//ss:Row", NS) or table.findall("Row"):
        celdas = []
        for cell in row.findall(".//ss:Cell", NS) or row.findall("Cell"):
            data = cell.find(".//ss:Data", NS) or cell.find("Data")
            text = data.text.strip() if data is not None and data.text else ""
            celdas.append(text)
        if celdas:
            filas.append(celdas)
    return filas
