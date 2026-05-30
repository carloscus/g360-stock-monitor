# g360-stock-monitor

Monitoreo de stock en tiempo real desde S1 (ERP CIPSA) con visualización por almacenes, líneas de producto y categorías. Incluye detección de transferencias sugeridas entre almacenes con alertas por desbalance y stock crítico.

> Powered by G360

---

## Índice

1. [Arquitectura](#1-arquitectura)
2. [Data Flow](#2-data-flow)
3. [Estructura del Proyecto](#3-estructura-del-proyecto)
4. [Features](#4-features)
5. [Health Filter (Umbrales por Cajas)](#5-health-filter-umbrales-por-cajas)
6. [Almacenes: Roles y Display](#6-almacenes-roles-y-display)
7. [Transferencias Sugeridas](#7-transferencias-sugeridas)
8. [Portable](#8-portable)
9. [Configuración](#9-configuración)
10. [Dependencias](#10-dependencias)
11. [Ejecución](#11-ejecución)
12. [Decision Log](#12-decision-log)

---

## 1. Arquitectura

```
┌──────────────────────────────────────────────────────────────┐
│                    Flet Desktop App (0.85.2)                  │
│  ┌──────────┐  ┌──────────────────────────────────────────┐  │
│  │ Sidebar  │  │              Main Content                 │  │
│  │ (200px)  │  │  Header + KPIs + Transfers + Cards + Cat │  │
│  └──────────┘  └──────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  src/core/                                             │  │
│  │    s1_downloader.py → descarga Excel desde S1          │  │
│  │    xls_fallback.py   → parsea Excel (5 engines)        │  │
│  │    processor.py      → KPIs, métricas, transferencias  │  │
│  │    constants.py      → URL, rutas                      │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### Capas

| Capa | Archivo | Responsabilidad |
|------|---------|-----------------|
| **Entry** | `main.py` | Boot, sys.path, `ft.run(main)` |
| **App** | `src/app.py` | Page setup, ciclo de vida, orquestación download → update |
| **Core** | `src/core/s1_downloader.py` | HTTP GET a S1, temp file, parse |
| **Core** | `src/core/xls_fallback.py` | 5 motores de lectura Excel (openpyxl, xlrd, csv, html, xml) |
| **Core** | `src/core/processor.py` | KPIs por almacén, líneas, categorías, transferencias |
| **UI** | `src/ui/dashboard.py` | Layout completo, sidebar, chips, KPIs, dialogs |
| **UI** | `src/ui/warehouse_card.py` | Card por almacén con display condicional (DESAGREGADO/CONSOLIDADO/PCT) |
| **UI** | `src/ui/linea_section.py` | Categorías → líneas → cards interactivas |
| **Config** | `src/config/theme.py` | Paleta esmeralda `#10B981`, colores, utility rgba |
| **Config** | `src/core/constants.py` | S1_URL, rutas assets |

### Patrones

- **Callback-based**: `Dashboard.set_on_refresh(cb)`, `on_linea_click`, `on_click`
- **Snapshot diff**: cada warehouse guarda su `disponible_total` previo en JSON → muestra tendencia (↑↓)
- **Búsqueda lazy**: search filtra en `_apply_filters()` con iteración sobre `_raw_data`
- **Chips toggle**: `_selected_alms` set, toggle visual sin recrear (muta bgcolor interno)

---

## 2. Data Flow

```
S1 (HTTP) → Excel (19 cols) → xls_fallback (5 engines) → dict[str, dict[str, dict]]
                                    ↓
                            processor.py
                          ┌─ calcular_kpis_almacen(raw)
                          ├─ obtener_metricas_lineas(kpis)
                          ├─ obtener_metricas_categorias(kpis)
                          ├─ contar_sin_linea(raw)
                          └─ sugerir_transferencias(raw, config, search)
                                    ↓
                             dashboard.py
                          ┌─ _build_kpi_row() → 6 KPIs
                          ├─ warehouse cards
                          ├─ linea_section
                          ├─ sidebar chips
                          └─ _transfer_section
```

### Formato de datos crudos (`_raw_data`)

```python
{
  "VES": {
    "016763": {
      "stock": 160,
      "predespacho": 20,
      "disponible": 140,
      "descripcion": "LAPICERO AZUL 0.5",
      "sku_unit": "UND"
    },
    ...
  },
  "121": { ... },   # QC/Inspección
  "129": { ... },   # Outlet
  "40":  { ... },   # APT
  "92":  { ... },   # Inspección externo
  "106": { ... },   # Outlet externo
  "118": { ... },   # Almacén 118
  "122": { ... },   # Exportación
}
```

### Catálogo (`catalogo_productos.json`)

```json
{
  "productos": [
    {
      "sku": "016763",
      "linea": "ESCRITURA",
      "categoria": "VINIBALL",
      "un_bx": 12,
      ...
    }
  ]
}
```

1088 productos reales. ~3062 SKUs en S1 → ~1277 caen en "SIN LINEA" / "OTROS".

---

## 3. Estructura del Proyecto

```
g360-stock-monitor/
├── main.py                          # Entry point
├── pyproject.toml                   # Python project metadata
├── requirements.txt                 # Pip deps (flet, requests, xlrd, openpyxl, bs4)
├── run.bat                          # Launcher con uv
├── skill.json                       # Skill descriptor (cola: cipsa, portable: true)
├── assets/
│   ├── data/
│   │   ├── lineas.json              # Config almacenes + líneas + umbrales
│   │   ├── catalogo_productos.json  # 1088 productos de CIPSA
│   │   ├── sample_data.json         # Fallback offline
│   │   └── _snapshot_*.json         # Snapshots por almacén (autogenerado)
│   └── images/
│       ├── Logo_cipsa_solid.svg     # Logo en sidebar
│       ├── Logo_cipsa_borde.svg     # Logo alternativo
│       └── cipsa.ico                # Icono de la aplicación (CIPSA)
├── src/
│   ├── app.py                       # StockMonitorApp (orquestador)
│   ├── config/
│   │   └── theme.py                 # Paleta esmeralda, rgba utility
│   ├── core/
│   │   ├── constants.py             # S1_URL, rutas absolutas
│   │   ├── s1_downloader.py         # Download + parse S1 Excel
│   │   ├── xls_fallback.py          # 5 motores de lectura Excel
│   │   └── processor.py             # KPI engine, métricas, transferencias
│   └── ui/
│       ├── dashboard.py             # Layout + interactividad
│       ├── warehouse_card.py        # Card de almacén (3 tipos display)
│       └── linea_section.py         # Categorías → líneas
├── g360-stock-monitor-portable/     # Distribución portable (ver sección 8)
│   ├── run.bat                      # Launcher 5 pasos (uv → Python → deps → update + shortcut → app)
│   ├── build-portable.bat           # PyInstaller EXE
│   ├── create_shortcut.vbs          # Acceso directo (WindowStyle=7, icono cipsa.ico)
│   ├── sync_portable.py             # Sincronización desde raíz
│   ├── .python-version
│   ├── main.py, src/, assets/       # Sincronizado desde raíz
│   └── ...
└── .venv/                           # Virtual environment (dev)
```

---

## 4. Features

### 4.1 Dashboard General

| Elemento | Descripción | Interacción |
|----------|-------------|-------------|
| **Header** | Logo CIPSA + título + loading + botón Actualizar | — |
| **KPIs** | Almacenes / SKUs / Disponible / Predespacho / Alertas / Críticos | Click → diálogo detalle |
| **Transferencias** | SKUs críticos o desbalanceados entre VES y secundarios | Click por SKU no, solo tabla |
| **Warehouse Cards** | Una card por almacén activo (métricas + alertas + tendencia) | Click → tabla SKU-level |
| **Categorías** | VINIBALL, VINIFAN, REPRESENTADAS con sus líneas | Click en línea → SKUs detalle |
| **Sidebar** | Search + chips almacén + SKUs sin cat + settings ⚙️ | Toggle chips filtra data |
| **Health Pills** | Filtro por salud (Crítico/Alerta/OK) usando umbrales por cajas | Píldoras en cabecera |

### 4.2 KPIs Clickables (6 diálogos)

| KPI | Color | Contenido del Diálogo |
|-----|-------|----------------------|
| **Almacenes** | `#10B981` | Tabla: código, stock, predespacho, disponible, alertas/críticos |
| **SKUs** | `#3b82f6` | Desglose por categoría (nombre, SKUs, disponible) |
| **Disponible** | `#34d399` | Top 15 líneas por disponible |
| **Predespacho** | `#f59e0b` | Top 15 líneas por predespacho con ratio % |
| **Alertas** | `#f59e0b` | SKUs en alerta (1 a 5 cajas) con paginación y ordenamiento |
| **Críticos** | `#ef4444` | SKUs críticos (< 1 caja) con paginación y ordenamiento |

### 4.3 Warehouse Cards

Tres modos de display según `tipo_reporte`:

| Tipo | Almacenes | Muestra |
|------|-----------|---------|
| **DESAGREGADO** | VES, 129, 40 | Stock total / Predespacho / Barra ratio P/(P+D) / Disponible |
| **CONSOLIDADO** | 121 | Total stock / Disponible |
| **PCT** | 92, 106, 118, 122 | "Info stock: X de Y" — informativo sin detalle |

Cada card muestra:
- Código + badge de rol (PRINCIPAL / SECUNDARIO)
- Nombre real del almacén
- **Tendencia** (↑↓→) vs snapshot anterior (diferencia de disponible)
- Contadores de críticos (🔴) y alertas (🟡) — solo si `participa_control: true`

### 4.4 Líneas por Categoría

Solo 3 categorías principales:

```
VINIBALL ── Pelotas
         └─ Escritura
         └─ Metálica
         └─ Archivo
         └─ ...

VINIFAN ── Dibujo
        └─ Pintura
        └─ Pegamentos
        └─ ...

REPRESENTADAS ── Mascotas
              └─ Representadas
              └─ ...
```

Cada línea muestra: nombre, stock, disponible, SKUs, barra stock mínimo.

### 4.5 Sidebar

- Search field (busca en todos los almacenes, incluso EXTERNO)
- Chips de almacén: 🟢 = PRINCIPAL, 🔵 = SECUNDARIO, ⚪ = EXTERNO
- Chips EXTERNO desactivados por defecto al cargar
- Link "SKUs sin categoría (N)" → diálogo con detalle
- Settings ⚙️ → modal de prioridades de almacenes
- "Powered by G360" signature

---

## 5. Health Filter (Umbrales por Cajas)

El sistema clasifica cada SKU según su **disponible en relación a `un_bx`** (unidades por caja del catálogo):

| Estado | Condición | Color | Emoji |
|--------|-----------|-------|-------|
| **Crítico** | `disp < un_bx` (menos de 1 caja) | Rojo `#ef4444` | 🔴 |
| **Alerta** | `un_bx <= disp <= un_bx * 5` (1 a 5 cajas) | Amarillo `#f59e0b` | 🟡 |
| **OK** | `disp > un_bx * 5` (más de 5 cajas) | Verde `#34d399` | 🟢 |

### Píldoras de Filtro

Tres píldoras en la cabecera del dashboard: **Crítico** / **Alerta** / **OK** + **Todo** (por defecto).

- Al seleccionar una píldora, el dashboard completo se filtra: KPIs, warehouse cards, líneas y categorías solo muestran datos de SKUs en ese estado.
- Los diálogos de KPIs (Críticos / Alertas) **siempre muestran todos los items** sin importar el filtro activo.
- El filtro opera a nivel SKU usando el umbral por cajas (`un_bx`) del catálogo.

### Vista Principal

| Vista | Respeta Filtro |
|-------|---------------|
| KPIs (Almacenes, SKUs, Disponible, Predespacho) | ✅ |
| Warehouse Cards | ✅ |
| Líneas y Categorías | ✅ |
| Diálogo Críticos | ❌ (muestra todos) |
| Diálogo Alertas | ❌ (muestra todos) |

---

## 6. Almacenes: Roles y Display

### Config actual (`lineas.json`)

| Código | Nombre | Prioridad | Tipo Reporte | Rol | Control |
|--------|--------|-----------|--------------|-----|---------|
| **VES** | VES | 1 | DESAGREGADO | **PRINCIPAL** | ✅ |
| **121** | CLVES_INSPECCION | 2 | CONSOLIDADO | SECUNDARIO | ✅ |
| **129** | CLVES_OUTLET | 3 | DESAGREGADO | SECUNDARIO | ✅ |
| **40** | APT | 4 | DESAGREGADO | SECUNDARIO | ✅ |
| **118** | ALMACEN_118 | 5 | PCT | EXTERNO | ❌ |
| **92** | INSPECCION | 6 | PCT | EXTERNO | ❌ |
| **106** | OUTLET | 7 | PCT | EXTERNO | ❌ |
| **122** | EXPORTACION | 8 | PCT | EXTERNO | ❌ |

### Reglas de display

- **DESAGREGADO**: stock, predespacho, barra ratio, disponible — completo
- **CONSOLIDADO**: solo stock total y disponible — útil para QC (121)
- **PCT**: solo texto informativo — almacenes externos sin control operativo
- `participa_control: false` → oculta contadores de alertas/críticos en la card

---

## 7. Transferencias Sugeridas

### Modo Normal (sin búsqueda)

Para cada SKU en VES (PRINCIPAL), evalúa secundarios ordenados por importancia:

| Tipo | Condición | Icono | Acción |
|------|-----------|-------|--------|
| **Crítico** | VES disponible ≤ 5 **Y** secundario tiene disponible > 0 | ⚠️ | `Liberar QC en 121` o `Trasladar desde {cod}` |
| **Desbalance** | Secundario stock ≥ 3× VES stock **Y** VES disp > 5 | ⚖️ | `Liberar QC en 121` o `Trasladar desde {cod}` |

Solo se muestra **el primer secundario** que cumple alguna condición por SKU.

### Modo Búsqueda

Al escribir en search, muestra el SKU en **todos los almacenes ordenados por importancia**:

```
SKU | Producto | Almacén | Rol | Stock | Disponible
```

---

## 8. Portable

El proyecto incluye `g360-stock-monitor-portable/` para distribución a PCs sin Python.

### Contenido

| Archivo | Propósito |
|---------|-----------|
| `run.bat` | Launcher 5 pasos: 1) instala uv si falta, 2) instala Python 3.11 si falta, 3) crea .venv + sincroniza deps, 4) verifica Windows Update + crea acceso directo (minimizado), 5) inicia la app |
| `build-portable.bat` | Genera .exe standalone con PyInstaller (icono cipsa.ico) |
| `create_shortcut.vbs` | Crea acceso directo en el escritorio (ventana minimizada, icono CIPSA) |
| `.python-version` | Versión de Python requerida |
| `requirements.txt` | Dependencias del proyecto |
| `sync_portable.py` | Script para sincronizar src/ y assets/ desde el proyecto raíz |

### Sincronización

```bash
# Desde la raíz del proyecto
python sync_portable.py
```

### Ejecución en PC destino

```bash
# Opción 1: Con run.bat (Windows, recomendado)
g360-stock-monitor-portable\run.bat

# Opción 2: Build EXE
g360-stock-monitor-portable\build-portable.bat
```

### Launcher `run.bat` (5 pasos)

| Paso | Acción | Auto-instala si falta |
|------|--------|-----------------------|
| 1/5 | **uv** | `powershell irm ... \| iex` |
| 2/5 | **Python 3.11** | `uv python install 3.11` |
| 3/5 | **.venv + dependencias** | `uv venv + uv sync` |
| 4/5 | **Windows Update + acceso directo** | Verifica updates pendientes (COM); crea .lnk en escritorio |
| 5/5 | **Iniciar app** | Ejecuta `main.py` con captura de errores |

Cada error muestra un popup (`msg *`) incluso con la ventana minimizada. Log detallado en `run_log.txt`.

### Requisitos en PC destino

- **Windows 10/11 x64**
- No requiere Python, uv, ni VC++ Redist pre-instalados
- Si falta VC++ Redist, la app falla con mensaje claro y se puede instalar manualmente

---

## 9. Configuración

### `lineas.json`

```json
{
  "almacenes": {
    "VES": {
      "nombre": "VES",
      "prioridad": 1,
      "tipo_reporte": "DESAGREGADO",
      "rol": "PRINCIPAL",
      "participa_control": true
    }
  },
  "umbrales": {
    "bajo_stock_unidades": 10,
    "critico_stock_unidades": 5,
    "porcentaje_alerta": 20,
    "dias_tendencia": 7
  },
  "lineas": [
    {
      "codigo": "PELOTAS",
      "nombre": "Pelotas",
      "grupo": "DEPORTES",
      "stock_minimo": 300
    }
  ]
}
```

### `constants.py`

```python
S1_URL = "http://appweb.cipsa.com.pe:8054/.../DownloadFiles?value=..."
```

---

## 10. Dependencias

| Paquete | Versión | Uso |
|---------|---------|-----|
| flet | ≥0.23.0 (real: 0.85.2) | UI framework (desktop) |
| requests | ≥2.31.0 | HTTP download from S1 |
| xlrd | ≥2.0.0 | Leer .xls (engine #2) |
| openpyxl | ≥3.0.0 | Leer .xlsx (engine #1) + exportación |
| beautifulsoup4 | ≥4.0.0 | Leer HTML tables (engine #4) |

---

## 11. Ejecución

### Desarrollo

```bash
cd g360-stock-monitor
uv venv .venv --python 3.11
uv sync
.venv\Scripts\python main.py
```

### Launcher (`run.bat`)

- Auto-crea .venv con `uv`
- Auto-sync dependencias
- Ejecuta `main.py`
- Log en `run_log.txt`

### Portable

```bash
# Desde el directorio portable
cd g360-stock-monitor-portable
run.bat
```

---

## 12. Decision Log

| Fecha | Decisión | Alternativa | Razón |
|-------|----------|-------------|-------|
| May 2026 | `disponible` desde col19 | Calcular col14-col17 | VBA original usa col19 como fuente de confianza |
| May 2026 | Categorías filtradas (3) | Mostrar OTROS como categoría | OTROS sin línea no aporta valor; se cuenta aparte |
| May 2026 | `GestureDetector.on_tap` | `Container.on_click` | Flet 0.85 no propaga clicks a hijos |
| May 2026 | `page.show_dialog(dlg)` | `page.dialog = dlg; dlg.open = True` | API deprecada en Flet 0.85 |
| May 2026 | EXTERNO desactivados por defecto | Todos activos | Usuario no necesita ver almacenes externos a diario |
| May 2026 | Health filter por cajas (`un_bx`) | Umbral fijo en unidades | `un_bx` varía por producto; umbral fijo es impreciso |
| May 2026 | Alerta = 1-5 cajas | ≤ 10 unidades | Unificación con criterio VBA por cajas |
| May 2026 | KPI dialogs ignoran filtro de salud | Respetan filtro | Usuario necesita ver totales reales independientemente del filtro |
| May 2026 | Portable dir con sync script | Manual copy | Sincronización reproducible vía `sync_portable.py` |
| May 2026 | Launcher 5 pasos auto-instala uv + Python + deps | Requerir instalación manual | Experiencia zero-setup en PC limpia |
| May 2026 | Eliminado chequeo VC++ Redist del launcher | Descarga automática de 25MB | `reg query` y `if exist` causaban cuelgues; la app muestra error claro si falta |
| May 2026 | Windows Update check en paso 4 | Omitir verificación | PowerShell COM `Microsoft.Update.Session` — rápido (~2s), informativo, no bloquea |
| May 2026 | Shortcut con `WindowStyle = 7` + icono `cipsa.ico` | Ventana normal + icono G360 | La app se lanza minimizada con icono de CIPSA |
| May 2026 | `msg *` popups en todos los errores del launcher | Solo `echo + pause` | Visible incluso con ventana CMD minimizada |
