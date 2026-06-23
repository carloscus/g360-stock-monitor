from __future__ import annotations

import flet as ft
from src.config.theme import get_colors, ACCENT, ACCENT_DARK, rgba
from src.core.processor import (
    load_lineas,
    calcular_kpis_almacen,
    obtener_metricas_lineas,
    obtener_metricas_categorias,
    contar_sin_linea,
    sugerir_transferencias,
    export_to_excel,
    reload_catalogo,
    update_catalogo_sku,
    _sku_info,
)
from src.ui.warehouse_card import WarehouseCard
from src.ui.linea_section import LineaSection

try:
    from g360_flet.g360_signature import G360Signature
except ImportError:
    G360Signature = None


class Dashboard:
    def __init__(self, page: ft.Page, theme_mode: str = "dark"):
        self.page = page
        self._theme_mode = theme_mode
        self.c = get_colors(self._theme_mode)
        self._warehouse_cards: ft.Column | None = None
        self._cat_section: ft.Container | None = None
        self._kpi_row: ft.Row | None = None
        self._header: ft.Container | None = None
        self._sidebar: ft.Container | None = None
        self._sidebar_chips: ft.Column | None = None
        self._main_container: ft.Container | None = None
        self._body_listview: ft.ListView | None = None
        self._main_content_area: ft.Container | None = None
        self._sin_cat_badge_text: ft.Text | None = None
        self._search_field = ft.TextField(
            hint_text="Buscar SKU o descripción...",
            prefix_icon=ft.Icons.SEARCH,
            border_radius=8,
            height=40,
            text_size=13,
            dense=True,
            border=ft.InputBorder.OUTLINE,
            border_color=self.c["border"],
            focused_border_color=ACCENT,
            cursor_color=ACCENT,
            hint_style=ft.TextStyle(size=13, color=self.c["text_muted"]),
            on_change=lambda e: self._on_search(),
            expand=True,
        )
        self._selected_alms: set[str] = set()
        self._transfer_section = ft.Container(visible=False)
        self._transfer_collapsed = False
        self._sin_cat_count = 0
        self._file_picker = ft.FilePicker()
        self._catalog_picker = ft.FilePicker()
        self._filtro_salud = "todo"
        self._theme_button: ft.IconButton | None = None
        self._filtro_salud_row = ft.Container()
        self._build_filtro_salud()
        self._ts_text = ft.Text(
            "", size=11, color=self.c["text_muted"], weight=ft.FontWeight.W_500,
        )
        self.status_text = ft.Text(
            "Cargue datos de stock para comenzar",
            size=13, color=self.c["text_muted"], weight=ft.FontWeight.W_500,
        )
        self._raw_data: dict | None = None
        self._kpis_alm: dict | None = None
        self._lineas: list | None = None
        self._categorias: list | None = None

    def build(self) -> ft.Container:
        self._init_loading()
        self._header = self._build_header()
        self._kpi_row = self._build_kpi_row({})
        self._warehouse_cards = ft.Column(spacing=10)
        self._cat_section = ft.Container(visible=False)

        self._body_listview = ft.ListView(
            controls=[
                self._warehouse_cards,
                ft.Divider(height=1, color=self.c["border"]),
                self._cat_section,
            ],
            padding=ft.Padding(left=20, right=20, top=0, bottom=0),
            expand=True,
            spacing=8,
        )
        self._body_listview.bgcolor = self.c["background"]
        
        self._main_content_area = ft.Container(
            content=ft.Column([
                self._header,
                self._loading_bar,
                self._kpi_row,
                self._transfer_section,
                self._body_listview,
                ft.Container(
                    content=self.status_text,
                    padding=ft.Padding(left=20, right=20, top=6, bottom=6),
                ),
            ], spacing=0),
            expand=True,
            bgcolor=self.c["background"],
        )
        self._sidebar = self._build_sidebar()
        self._main_container = ft.Container(
            content=ft.Row([self._sidebar, self._main_content_area], spacing=0),
            expand=True,
            bgcolor=self.c["background"],
        )
        # En Flet 0.85+, los servicios (FilePicker) se registran automáticamente vía Service.init()

        return self._main_container

    def _build_sidebar(self) -> ft.Container:
        self._sin_cat_badge_text = ft.Text("", size=10, color="white", weight=ft.FontWeight.W_700)
        self._sin_cat_badge = ft.Container(
            content=self._sin_cat_badge_text,
            bgcolor=self.c["warning"], border_radius=8,
            padding=ft.Padding(left=6, right=6, top=2, bottom=2),
            visible=False,
        )
        self._sidebar_chips = ft.Column(spacing=3, scroll=ft.ScrollMode.AUTO, expand=True)
        self._theme_button = ft.IconButton(
            icon=ft.Icons.DARK_MODE if self._theme_mode == "dark" else ft.Icons.LIGHT_MODE,
            icon_size=16,
            icon_color=self.c["text_muted"],
            on_click=lambda _: self._on_theme_toggle_click(),
            tooltip="Tema claro/oscuro",
        )
        
        # Construcción limpia del sidebar sin referencias a los pickers en los controls
        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=self._search_field,
                    padding=ft.Padding(left=8, right=8, top=14, bottom=8),
                ),
                ft.Container(
                    content=ft.Text("ALMACENES", size=10, color=self.c["text_muted"], weight=ft.FontWeight.W_700),
                    padding=ft.Padding(left=12, right=12, top=6, bottom=4),
                ),
                self._sidebar_chips,
                ft.Divider(height=1, color=self.c["border"]),
                ft.Container(
                    content=ft.GestureDetector(
                        content=ft.Row([
                            ft.Icon(ft.Icons.HELP_OUTLINE, size=14, color=self.c["warning"]),
                            ft.Text("SKUs sin categoría", size=10, color=self.c["text_muted"]),
                            ft.Container(expand=True),
                            self._sin_cat_badge,
                        ], spacing=4),
                        on_tap=lambda e: self._show_sin_linea_dlg(),
                        mouse_cursor=ft.MouseCursor.CLICK,
                    ),
                    padding=ft.Padding(left=12, right=12, top=8, bottom=8),
                ),
                self._filtro_salud_row,
                ft.Container(expand=True),
                ft.Divider(height=1, color=self.c["border"]),
                ft.Container(
                    content=ft.Row([
                        ft.IconButton(
                            icon=ft.Icons.SETTINGS,
                            icon_size=16,
                            icon_color=self.c["text_muted"],
                            on_click=self._open_config,
                            tooltip="Configurar almacenes",
                        ),
                        self._theme_button,
                        ft.Container(expand=True),
                        G360Signature(mode="powered", version="2.0") if G360Signature
                        else ft.Text("Powered by G360", size=10, color=rgba(ACCENT, 0.4), weight=ft.FontWeight.W_600),
                    ], spacing=0),
                    padding=ft.Padding(left=4, right=8, top=6, bottom=6),
                ),
            ], spacing=0),
            width=200,
            bgcolor=self.c["surface"],
            border=ft.Border(right=ft.BorderSide(1, self.c["border"])),
        )

    def _init_loading(self):
        self._loading_bar = ft.Container(
            visible=False,
            content=ft.Row([
                ft.ProgressRing(width=22, height=22, stroke_width=3, color="white"),
                ft.Text("Procesando...", size=14, weight=ft.FontWeight.W_700, color="white"),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=ACCENT,
            border_radius=0,
            padding=ft.Padding(left=20, right=20, top=10, bottom=10),
            animate_opacity=300,
        )

    def set_loading(self, active: bool, msg: str = ""):
        self._loading_bar.visible = active
        if msg and self._loading_bar.content and len(self._loading_bar.content.controls) > 1:
            self._loading_bar.content.controls[1].value = msg
        self.page.update()

    def _build_header(self):
        logo = ft.Image(
            src="assets/images/Logo_cipsa_solid.svg",
            width=32, height=32, fit=ft.BoxFit.CONTAIN,
        )
        self._ts_badge = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.SCHEDULE, size=14, color=rgba(ACCENT, 0.7)),
                self._ts_text,
            ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            visible=False,
            padding=ft.Padding(left=10, right=10, top=5, bottom=5),
            bgcolor=rgba(ACCENT, 0.06),
            border_radius=8,
        )
        return ft.Container(
            content=ft.Row([
                logo,
                ft.Text("Stock Monitor", size=20, weight=ft.FontWeight.W_800, color=self.c["accent"]),
                ft.Text("CIPSA", size=11, color=self.c["text_muted"], weight=ft.FontWeight.W_300),
                ft.Container(expand=True),
                self._ts_badge,
                ft.ElevatedButton(
                    "Actualizar",
                    icon=ft.Icons.REFRESH,
                    style=ft.ButtonStyle(
                        color={"": "#ffffff"},
                        bgcolor={"": ACCENT, "hovered": ACCENT_DARK},
                        shape=ft.RoundedRectangleBorder(radius=10),
                        padding=ft.Padding(left=18, right=18, top=11, bottom=11),
                    ),
                    on_click=self._on_refresh,
                ),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding(left=24, right=24, top=12, bottom=12),
            bgcolor=self.c["surface"],
            border=ft.Border(bottom=ft.BorderSide(1, self.c["border"])),
        )

    async def _on_refresh(self, e):
        if self._on_refresh_cb:
            cb = self._on_refresh_cb()
            if hasattr(cb, '__await__'):
                await cb
            else:
                cb()

    def set_on_theme_toggle(self, callback):
        self._on_theme_toggle_cb = callback

    def _on_theme_toggle_click(self):
        if hasattr(self, "_on_theme_toggle_cb"):
            self._on_theme_toggle_cb()

    def update_theme(self, theme_mode: str):
        self._theme_mode = theme_mode
        self.c = get_colors(theme_mode)
        
        # Actualizar fondos principales
        if self._main_container:
            self._main_container.bgcolor = self.c["background"]
        if self._main_content_area:
            self._main_content_area.bgcolor = self.c["background"]
        if self._body_listview:
            self._body_listview.bgcolor = self.c["background"]
            
        # Actualizar Sidebar
        self._sidebar.bgcolor = self.c["surface"]
        self._sidebar.border = ft.Border(right=ft.BorderSide(1, self.c["border"]))
        
        # Actualizar Header
        self._header.bgcolor = self.c["surface"]
        self._header.border = ft.Border(bottom=ft.BorderSide(1, self.c["border"]))

        # Actualizar fila de KPIs (esto soluciona el fondo oscuro residual en tema claro)
        if self._kpi_row:
            self._kpi_row.bgcolor = self.c["surface"]
            self._kpi_row.border = ft.Border(bottom=ft.BorderSide(1, self.c["border"]))

        # Actualizar componentes de entrada
        self._search_field.border_color = self.c["border"]
        self._search_field.hint_style = ft.TextStyle(size=13, color=self.c["text_muted"])
        
        # Actualizar iconos
        self._update_theme_button_icon()
        
        # Actualizar texto de carga para contraste en tema claro
        if self._loading_bar and self._loading_bar.content:
            self._loading_bar.content.controls[1].color = self.c["text_primary"]

        # Refrescar datos para re-renderizar cards con nuevos colores
        if self._raw_data:
            self._apply_filters()
        else:
            self.page.update()

    def _update_theme_button_icon(self):
        if self._theme_button:
            self._theme_button.icon = ft.Icons.LIGHT_MODE if self._theme_mode == "light" else ft.Icons.DARK_MODE

    def set_on_refresh(self, callback):
        self._on_refresh_cb = callback

    def _rebuild_sidebar(self):
        self._sidebar.bgcolor = self.c["surface"]
        self._sidebar.border = ft.Border(right=ft.BorderSide(1, self.c["border"]))
        self.page.bgcolor = self.c["background"]
        self._build_header()
        if self._search_field:
            self._search_field.border_color = self.c["border"]
            self._search_field.focused_border_color = ACCENT
            self._search_field.cursor_color = ACCENT
        self.page.update()

    def _open_config(self, e):
        self._show_config_dialog()

    def _show_config_dialog(self):
        config = load_lineas()
        alm_config = config.get("almacenes", {})
        rows = []
        prio_entries = {}
        rol_entries = {}

        sort_order = {"PRINCIPAL": 0, "SECUNDARIO": 1, "EXTERNO": 2}
        sorted_codes = sorted(alm_config.keys(), key=lambda c: (sort_order.get(alm_config[c].get("rol", ""), 9), alm_config[c].get("prioridad", 99)))

        rows.append(ft.Container(
            content=ft.Row([
                ft.Text("Cód", size=11, weight=ft.FontWeight.W_700, color=self.c["accent"], width=50),
                ft.Text("Nombre Almacén", size=11, weight=ft.FontWeight.W_700, color=self.c["accent"], expand=True),
                ft.Text("Reporte", size=11, weight=ft.FontWeight.W_700, color=self.c["accent"], width=85),
                ft.Text("Rol Operativo", size=11, weight=ft.FontWeight.W_700, color=self.c["accent"], width=110),
                ft.Text("Prio", size=11, weight=ft.FontWeight.W_700, color=self.c["accent"], width=50),
            ], spacing=8),
            bgcolor=rgba(self.c["accent"], 0.08), border_radius=6,
            padding=ft.Padding(left=8, right=8, top=6, bottom=6),
        ))

        for cod in sorted_codes:
            cfg = alm_config[cod]
            prio = ft.TextField(
                value=str(cfg.get("prioridad", "")),
                width=50, height=36, text_size=12,
                text_align=ft.TextAlign.CENTER, dense=True,
            )
            
            rol_dropdown = ft.Dropdown(
                value=cfg.get("rol", "EXTERNO"),
                options=[
                    ft.dropdown.Option("PRINCIPAL"),
                    ft.dropdown.Option("SECUNDARIO"),
                    ft.dropdown.Option("EXTERNO"),
                ],
                width=110, height=36, text_size=11,
                dense=True,
                border_radius=8,
            )
            
            prio_entries[cod] = prio
            rol_entries[cod] = rol_dropdown
            
            tipo_color = {"DESAGREGADO": ACCENT, "CONSOLIDADO": "#3b82f6", "PCT": "#8b5cf6"}
            rows.append(ft.Container(
                content=ft.Row([
                    ft.Text(cod, size=13, weight=ft.FontWeight.W_700, width=50, color=self.c["text_primary"]),
                    ft.Text(cfg.get("nombre", ""), size=11, color=self.c["text_muted"], expand=True),
                    ft.Container(
                        content=ft.Text(cfg.get("tipo_reporte", ""), size=10, color="white", weight=ft.FontWeight.W_600), 
                        bgcolor=tipo_color.get(cfg.get("tipo_reporte", ""), "#666"), 
                        border_radius=5, padding=ft.Padding(left=6, right=6, top=2, bottom=2),
                        width=85, alignment=ft.Alignment.CENTER
                    ),
                    rol_dropdown,
                    prio,
                ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.Padding(left=4, right=4, top=6, bottom=6),
                border=ft.Border(bottom=ft.BorderSide(1, self.c["border"])) if cod != sorted_codes[-1] else None
            ))

        def save(e):
            for cod in alm_config.keys():
                try:
                    config["almacenes"][cod]["prioridad"] = int(prio_entries[cod].value.strip())
                    config["almacenes"][cod]["rol"] = rol_entries[cod].value
                except (ValueError, AttributeError, KeyError):
                    pass
            from src.core.constants import LINEAS_FILE
            import json
            with open(LINEAS_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self.page.pop_dialog()
            self._apply_filters() # Refrescar la vista principal con nuevos roles

        async def _on_catalog_import(e):
            files = await self._catalog_picker.pick_files(allowed_extensions=["json"])
            if files:
                try:
                    import json
                    import shutil
                    from src.core.constants import DATA_DIR
                    src_path = files[0].path
                    dest_path = DATA_DIR / "catalogo_productos.json"
                    with open(src_path, encoding="utf-8") as f:
                        test_data = json.load(f)
                        if "productos" not in test_data:
                            raise ValueError("El archivo no contiene la clave 'productos'")
                    shutil.copy(src_path, dest_path)
                    reload_catalogo()
                    self.page.pop_dialog()
                    self._show_snack("Catálogo actualizado e importado con éxito")
                    self._apply_filters()
                except Exception as ex:
                    self._show_snack(f"Error al cargar catálogo: {ex}", is_error=True)

        catalog_btn = ft.ElevatedButton(
            "Importar Nuevo Catálogo JSON",
            icon=ft.Icons.UPLOAD_FILE,
            on_click=_on_catalog_import,
            style=ft.ButtonStyle(bgcolor={"": self.c["surface_variant"]}, color={"": self.c["text_primary"]})
        )

        dlg = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.Icons.TUNE, color=ACCENT), ft.Text("Configuración de Almacenes", weight=ft.FontWeight.W_800, size=16)]),
            content=ft.Container(
                content=ft.Column([
                    ft.Column(rows, spacing=0, scroll=ft.ScrollMode.AUTO, expand=True),
                    ft.Divider(height=16, color=rgba(self.c["border"], 0.5)),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("CATÁLOGO DE PRODUCTOS", size=10, weight=ft.FontWeight.W_700, color=self.c["accent"]),
                            catalog_btn,
                        ], spacing=6),
                        padding=ft.Padding(left=4, right=4, top=0, bottom=4),
                    ),
                ], spacing=8),
                width=680, height=480
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: self.page.pop_dialog()), 
                ft.ElevatedButton("Guardar Cambios", on_click=save, bgcolor=ACCENT, color="white",
                                  style=ft.ButtonStyle(overlay_color=rgba(ACCENT, 0.1), elevation=0)),
            ],
        )
        self.page.show_dialog(dlg)

    def _sidebar_chip(self, cod: str, rol: str, selected: bool) -> ft.Container:
        rol_color = {"PRINCIPAL": ACCENT, "SECUNDARIO": "#3b82f6", "EXTERNO": "#6b7280"}
        base = rol_color.get(rol, "#666")
        inner = ft.Container(
            content=ft.Row([
                ft.Container(width=8, height=8, bgcolor=base if selected else rgba(base, 0.4), border_radius=4),
                ft.Text(cod, size=12, weight=ft.FontWeight.W_600 if selected else ft.FontWeight.W_400, color=self.c["text_primary"] if selected else rgba(self.c["text_primary"], 0.5)),
                ft.Container(expand=True),
                ft.Text(rol[:4], size=10, color=rgba(base, 0.6)),
            ], spacing=6),
            border_radius=6,
            bgcolor=rgba(base, 0.08) if selected else "transparent",
            padding=ft.Padding(left=10, right=10, top=5, bottom=5),
        )
        return ft.GestureDetector(
            content=inner,
            on_tap=lambda e, c=cod: self._on_chip_toggle(c),
            mouse_cursor=ft.MouseCursor.CLICK,
        )

    def _build_filtro_salud(self):
        opts = [("todo", "Todo"), ("ok", "OK"), ("alerta", "Alerta"), ("critico", "Crítico")]
        pills = []
        for val, label in opts:
            is_active = val == self._filtro_salud
            pill = ft.GestureDetector(
                content=ft.Container(
                    content=ft.Text(label, size=10, weight=ft.FontWeight.W_700 if is_active else ft.FontWeight.W_500,
                                    color="white" if is_active else self.c["text_muted"]),
                    padding=ft.Padding(left=8, right=8, top=4, bottom=4),
                    bgcolor=self.c["accent"] if is_active else rgba(self.c["text_muted"], 0.08),
                    border_radius=12,
                ),
                on_tap=lambda e, v=val: self._on_filtro_salud(v),
                mouse_cursor=ft.MouseCursor.CLICK,
            )
            pills.append(pill)
        self._filtro_salud_row.content = ft.Column([
            ft.Text("Filtrar salud", size=9, weight=ft.FontWeight.W_600, color=self.c["text_muted"]),
            ft.Row(pills, spacing=4, wrap=True),
        ], spacing=4)

    def _on_filtro_salud(self, val: str):
        self._filtro_salud = val
        self._build_filtro_salud()
        self._apply_filters()

    def _on_chip_toggle(self, cod: str):
        if cod in self._selected_alms:
            if len(self._selected_alms) > 1:
                self._selected_alms.discard(cod)
        else:
            self._selected_alms.add(cod)
        self._apply_filters()

    def _on_search(self):
        self._apply_filters()

    def _get_filtered_raw(self) -> dict:
        if not self._raw_data:
            return {}
        return {k: v for k, v in self._raw_data.items() if k in self._selected_alms}

    def _filter_by_health(self, raw: dict) -> dict:
        if self._filtro_salud == "todo":
            return raw
        result = {}
        for alm, skus in raw.items():
            if not isinstance(skus, dict):
                continue
            matched = {}
            for sku, info in skus.items():
                if not isinstance(info, dict):
                    continue
                try:
                    disp = info.get("disponible", info["stock"] - info["predespacho"])
                    if self._match_filtro_sku(sku, disp):
                        matched[sku] = info
                except Exception:
                    matched[sku] = info
            if matched:
                result[alm] = matched
        return result

    def _apply_filters(self):
        if not self._raw_data:
            return
        raw = self._get_filtered_raw()
        try:
            raw = self._filter_by_health(raw)
        except Exception:
            pass
        search = (self._search_field.value or "").strip().lower()
        if search:
            filtered = {}
            for alm, skus in raw.items():
                matched = {}
                for sku, info in skus.items():
                    desc = (info.get("descripcion", "") or "").lower()
                    if search in sku.lower() or search in desc:
                        matched[sku] = info
                if matched:
                    filtered[alm] = matched
            raw = filtered if filtered else raw

        # Rebuild UI with filtered data
        self._kpis_alm = calcular_kpis_almacen(raw)
        config = load_lineas()
        alm_config = config.get("almacenes", {})
        self._lineas = obtener_metricas_lineas(self._kpis_alm, alm_config)
        self._categorias = obtener_metricas_categorias(self._kpis_alm)
        sin_linea = contar_sin_linea(raw)

        total_disp = sum(a["disponible_total"] for a in self._kpis_alm.values())
        total_pre = sum(a["predespacho_total"] for a in self._kpis_alm.values())
        total_alertas = sum(a["alertas"] for a in self._kpis_alm.values())
        total_criticos = sum(a["criticos"] for a in self._kpis_alm.values())
        total_over = sum(a.get("sobre_comprometidos", 0) for a in self._kpis_alm.values())
        total_skus = sum(a["sku_count"] for a in self._kpis_alm.values())

        self._kpi_row.content = self._build_kpi_row({
            "almacenes": len(self._kpis_alm), "skus": total_skus,
            "disponible": total_disp, "predespacho": total_pre,
            "alertas": total_alertas, "criticos": total_criticos,
            "sobre_comprometidos": total_over,
        }).content

        sorted_alms = sorted(self._kpis_alm.values(), key=lambda a: alm_config.get(a["codigo"], {}).get("prioridad", 99))
        cards = []
        for alm in sorted_alms:
            cfg = alm_config.get(alm["codigo"], {})
            card = WarehouseCard(alm, cfg, self.c, on_click=self._show_warehouse_skus)
            cards.append(card.build())
        self._warehouse_cards.controls = cards

        linea_section = LineaSection(self._lineas, self._categorias, self.c,
                                     on_linea_click=self._show_linea_skus,
                                     sin_linea=sin_linea,
                                     filtro_salud=self._filtro_salud)
        self._cat_section.content = linea_section.build()
        self._cat_section.visible = len(self._categorias) > 0

        # Update sidebar chip visuals
        for cod, gd in self._chip_refs.items():
            cfg = alm_config.get(cod, {})
            selected = cod in self._selected_alms
            rol = cfg.get("rol", "")
            rol_color = {"PRINCIPAL": ACCENT, "SECUNDARIO": "#3b82f6", "EXTERNO": "#6b7280"}
            base = rol_color.get(rol, "#666")
            inner = gd.content
            inner.bgcolor = rgba(base, 0.08) if selected else "transparent"
            row = inner.content
            if row and len(row.controls) >= 3:
                dot = row.controls[0]
                dot.bgcolor = base if selected else rgba(base, 0.4)
                txt = row.controls[1]
                txt.color = self.c["text_primary"] if selected else rgba(self.c["text_primary"], 0.5)
                txt.weight = ft.FontWeight.W_600 if selected else ft.FontWeight.W_400

        self._sin_cat_count = sin_linea
        if self._sin_cat_badge_text:
            self._sin_cat_badge_text.value = str(sin_linea) if sin_linea else ""
            self._sin_cat_badge.visible = bool(sin_linea)

        # Update filtro pills visual
        self._build_filtro_salud()

        search_raw = self._raw_data if search else raw
        transfers = sugerir_transferencias(search_raw, alm_config, umbral=5, search=search)
        self._build_transfer_section(transfers, bool(transfers), search)

    def _build_transfer_section(self, transfers: list, has_transfers: bool, search: bool):
        if not has_transfers and not search:
            self._transfer_section.visible = False
            return
        if search:
            t_rows = [self._dlg_header([("SKU", 65), ("Producto", True), ("Línea", 65), ("Alm", 40), ("Rol", 55), ("Stock", 55), ("Disp.", 60)])]
            for t in transfers[:20]:
                linea_txt = t.get("linea", "")[:12] or "-"
                rol_color = {"PRINCIPAL": ACCENT, "SECUNDARIO": "#3b82f6", "EXTERNO": "#6b7280"}
                rc = rol_color.get(t["rol"], "#666")
                sc = self._sku_state(t["sku"], t['disponible'])
                t_rows.append(self._dlg_row([
                    ft.Text(t["sku"], size=11, weight=ft.FontWeight.W_600, width=65),
                    ft.Text((t.get("descripcion", "") or "")[:50], size=12, color=self.c["text_muted"], expand=True),
                    ft.Text(linea_txt, size=11, width=65, color=self.c["text_muted"]),
                    ft.Text(t["almacen"], size=11, width=40, color=rc, text_align=ft.TextAlign.CENTER),
                    ft.Text(t["rol"], size=10, width=55, color=rgba(rc, 0.7), text_align=ft.TextAlign.CENTER),
                    ft.Text(f"{t['stock']:,}", size=11, width=55, text_align=ft.TextAlign.RIGHT),
                    ft.Text(f"{t['disponible']:,}", size=12, weight=ft.FontWeight.W_700, width=60, color=sc["color"], text_align=ft.TextAlign.RIGHT),
                ]))
            count_txt = f"{len(transfers)} resultados"
            title = f"SKU: '{self._search_field.value}'"
        else:
            t_rows = [self._dlg_header([("SKU", 65), ("Producto", True), ("VES", 65), ("Origen", 45), ("Disp.", 55), ("Sugerencia", True)])]
            for t in transfers[:10]:
                accion = f"Liberar QC en {t['secundario']}" if t['secundario'] == "121" else f"Trasladar desde {t['secundario']}"
                tipo_icon = "⚠️" if t["tipo"] == "critico" else "⚖️"
                t_rows.append(self._dlg_row([
                    ft.Text(t["sku"], size=11, weight=ft.FontWeight.W_600, width=65),
                    ft.Text((t.get("descripcion", "") or "")[:50], size=12, color=self.c["text_muted"], expand=True),
                    ft.Text(f"{t['p_disp']}/{t['p_stock']}", size=11, width=65, color=self.c["error"] if t['p_disp'] <= 2 else self.c["warning"], text_align=ft.TextAlign.CENTER),
                    ft.Text(t["secundario"], size=11, width=45, color="#3b82f6", text_align=ft.TextAlign.CENTER),
                    ft.Text(f"{t['s_disp']:,}", size=12, weight=ft.FontWeight.W_700, width=55, color=self.c["success"], text_align=ft.TextAlign.RIGHT),
                    ft.Text(f"{tipo_icon} {accion}", size=12, color=self.c["text_muted"], expand=True),
                ]))
            count_txt = f"{len(transfers)} sugerencias"
            title = "Transferencias Sugeridas"
        empty_note = ft.Container(height=0) if has_transfers else (
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=12, color=self.c["text_muted"]),
                    ft.Text("No hay SKUs con stock bajo en almacén principal que tengan stock en secundarios", size=10, color=self.c["text_muted"]),
                ], spacing=4),
                margin=ft.Margin(top=4, bottom=0, left=0, right=0),
            ) if search else ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.SEARCH_OFF, size=12, color=self.c["text_muted"]),
                    ft.Text(f"'{self._search_field.value}' no encontrado", size=10, color=self.c["text_muted"]),
                ], spacing=4),
                margin=ft.Margin(top=4, bottom=0, left=0, right=0),
            )
        )
        chevron = ft.Icon(ft.Icons.EXPAND_MORE if self._transfer_collapsed else ft.Icons.EXPAND_LESS,
                          size=18, color=self.c["text_muted"],
                          animate_rotation=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT))

        def _toggle_transfer(e):
            self._transfer_collapsed = not self._transfer_collapsed
            self._apply_filters()

        body = ft.Container(
            content=ft.Column([ft.Column(t_rows, spacing=1), empty_note], spacing=0),
            visible=not self._transfer_collapsed,
        )
        self._transfer_section.content = ft.Container(
            content=ft.Column([
                ft.GestureDetector(
                    content=ft.Row([
                        ft.Icon(ft.Icons.SWAP_HORIZ, size=16, color=self.c["warning"]),
                        ft.Text(title, size=13, weight=ft.FontWeight.W_700, color=self.c["text_primary"]),
                        ft.Container(expand=True),
                        ft.Text(count_txt, size=10, color=self.c["text_muted"]),
                        chevron,
                    ], spacing=6),
                    on_tap=_toggle_transfer,
                    mouse_cursor=ft.MouseCursor.CLICK,
                ),
                ft.Container(height=6),
                body,
            ], spacing=0),
            padding=ft.Padding(left=20, right=20, top=10, bottom=10),
            bgcolor=self.c["surface"],
            border=ft.Border(bottom=ft.BorderSide(1, self.c["border"])),
        )
        self._transfer_section.visible = True

        sin_linea_txt = f" • {self._sin_cat_count} SKUs sin categoría" if self._sin_cat_count else ""
        search_txt = f" • filtro: '{self._search_field.value}'" if search else ""
        status_parts = f"Datos actualizados — {len(self._kpis_alm)} almacenes, {len(self._categorias)} categorías, {len(self._lineas)} líneas"
        self.status_text.value = f"{status_parts}{sin_linea_txt}{search_txt}"
        self.status_text.color = self.c["accent"]
        self.page.update()

    def _build_kpi_row(self, kpis: dict) -> ft.Container:
        if not kpis:
            kpis = {"almacenes": 0, "skus": 0, "alertas": 0, "criticos": 0, "sobre_comprometidos": 0, "disponible": 0, "predespacho": 0}
        cards_row = ft.Row(spacing=10, controls=[
            self._clickable_kpi("Almacenes", str(kpis.get("almacenes", 0)), ft.Icons.WAREHOUSE, ACCENT, self._show_almacenes_dlg),
            self._clickable_kpi("SKUs", f"{kpis.get('skus', 0):,}", ft.Icons.INVENTORY_2, self.c["info"], self._show_skus_dlg),
            self._clickable_kpi("Disponible", f"{kpis.get('disponible', 0):,}", ft.Icons.CHECK_CIRCLE, self.c["success"], self._show_disp_dlg),
            self._clickable_kpi("Predespacho", f"{kpis.get('predespacho', 0):,}", ft.Icons.CALL_MADE, self.c["warning"], self._show_pred_dlg),
            self._clickable_kpi("Alertas", str(kpis.get("alertas", 0)), ft.Icons.WARNING_AMBER, self.c["warning"], self._show_alertas_dlg),
            self._clickable_kpi("Críticos", str(kpis.get("criticos", 0)), ft.Icons.ERROR_OUTLINE, self.c["error"], self._show_criticos_dlg),
            self._clickable_kpi("Sobre-comp.", str(kpis.get("sobre_comprometidos", 0)), ft.Icons.ASSIGNMENT_LATE, "#f97316", self._show_sobre_comprometidos_dlg),
        ])
        return ft.Container(
            content=cards_row, padding=ft.Padding(left=20, right=20, top=14, bottom=14),
            bgcolor=self.c["surface"], border=ft.Border(bottom=ft.BorderSide(1, self.c["border"])),
        )

    def _clickable_kpi(self, label: str, value: str, icon: str, color: str, on_click) -> ft.Container:
        icon_box = ft.Container(
            content=ft.Icon(icon, size=20, color="white"),
            bgcolor=rgba(color, 0.2),
            border_radius=8, padding=ft.Padding(left=8, right=8, top=7, bottom=7),
            shadow=ft.BoxShadow(blur_radius=8, color=rgba(color, 0.25), spread_radius=0),
        )
        inner = ft.Container(
            content=ft.Row([
                icon_box,
                ft.Column([ft.Text(value, size=18, weight=ft.FontWeight.W_800, color=self.c["text_primary"]), ft.Text(label, size=11, color=self.c["text_muted"], weight=ft.FontWeight.W_500)], spacing=1, expand=True),
            ], spacing=12),
            bgcolor=self.c["surface"],
            border_radius=8,
            border=ft.Border(top=ft.BorderSide(1, rgba(color, 0.15)), right=ft.BorderSide(1, rgba(color, 0.15)), bottom=ft.BorderSide(1, rgba(color, 0.15)), left=ft.BorderSide(1, rgba(color, 0.15))),
            padding=12,
            ink=True,
        )
        wrapper = ft.GestureDetector(
            content=inner,
            on_tap=lambda e: self._handle_kpi_click(on_click),
            mouse_cursor=ft.MouseCursor.CLICK,
            tooltip=f"Ver detalle de {label.lower()}",
        )
        return ft.Container(content=wrapper, padding=10, expand=True, bgcolor=self.c["surface"])

    def _show_snack(self, msg: str, is_error: bool = False):
        self.page.snack_bar = ft.SnackBar(
            content=ft.Row([
                ft.Icon(
                    ft.Icons.ERROR_OUTLINE if is_error else ft.Icons.CHECK_CIRCLE,
                    color="white", size=20
                ),
                ft.Text(msg, color="white", weight=ft.FontWeight.W_500, size=14),
            ], spacing=10),
            bgcolor=self.c["error"] if is_error else self.c["accent"],
            duration=4000,
            behavior=ft.SnackBarBehavior.FLOATING,
            width=500,
        )
        self.page.snack_bar.open = True
        self.page.update()

    def _handle_kpi_click(self, on_click):
        if not on_click:
            return
        if not self._raw_data:
            self._show_snack("Presione 'Actualizar' para cargar datos")
            return
        try:
            on_click()
        except Exception as ex:
            self._show_snack(f"Error: {ex}")

    # ─── Interactive Dialogs ───

    def _show_almacenes_dlg(self):
        if not self._kpis_alm:
            return
        rows = []
        for alm in sorted(self._kpis_alm.values(), key=lambda a: a["codigo"]):
            d = alm
            rows.append(self._dlg_row([
                ft.Text(d["codigo"], weight=ft.FontWeight.W_700, size=12, width=50),
                ft.Text(f"S:{d['stock_total']:,}", size=11, color=self.c["text_muted"]),
                ft.Text(f"P:{d['predespacho_total']:,}", size=11, color=rgba(self.c["warning"], 0.8)),
                ft.Text(f"D:{d['disponible_total']:,}", size=11, color=self.c["success"]),
                ft.Text(f"⚠{d['alertas']} ❌{d['criticos']}", size=10, color=self.c["text_muted"]),
            ]))
        self._show_dlg("Almacenes", rows, 350)

    def _show_skus_dlg(self):
        if not self._categorias:
            return
        rows = []
        for cat in self._categorias:
            rows.append(self._dlg_row([
                ft.Container(content=ft.Text(cat["categoria"], weight=ft.FontWeight.W_700, size=12), expand=True),
                ft.Text(f"{cat['skus']:,} SKUs", size=12, color=self.c["text_primary"]),
                ft.Text(f"D:{cat['disponible']:,}", size=11, color=self.c["success"]),
            ]))
        self._show_dlg("SKUs por Categoría", rows, 300)

    def _show_disp_dlg(self):
        if not self._lineas:
            return
        rows = [self._dlg_header([("Línea", True), ("Disponible", None), ("Stock", None), ("SKUs", None)])]
        for ln in self._lineas[:15]:
            rows.append(self._dlg_row([
                ft.Text(ln["nombre"], size=12, expand=True),
                ft.Text(f"{ln['disponible']:,}", size=12, weight=ft.FontWeight.W_700, color=self.c["success"]),
                ft.Text(f"{ln['stock']:,}", size=11, color=self.c["text_muted"]),
                ft.Text(str(ln["skus"]), size=11, color=self.c["text_muted"]),
            ]))
        self._show_dlg("Top Disponible por Línea", rows, 400)

    def _show_pred_dlg(self):
        if not self._lineas:
            return
        sorted_pred = sorted(self._lineas, key=lambda ln: ln["predespacho"], reverse=True)[:15]
        rows = [self._dlg_header([("Línea", True), ("Predespacho", None), ("Ratio", None)])]
        for ln in sorted_pred:
            total = ln["predespacho"] + ln["disponible"]
            ratio = f"{ln['predespacho']/total*100:.0f}%" if total > 0 else "0%"
            rows.append(self._dlg_row([
                ft.Text(ln["nombre"], size=12, expand=True),
                ft.Text(f"{ln['predespacho']:,}", size=12, weight=ft.FontWeight.W_700, color=self.c["warning"]),
                ft.Text(ratio, size=11, color=rgba(self.c["warning"], 0.7)),
            ]))
        self._show_dlg("Predespacho por Línea", rows, 400)

    def _show_alertas_dlg(self):
        raw = self._get_filtered_raw()
        if not raw or not self._kpis_alm:
            return
        items = []
        for alm, skus in raw.items():
            for sku, info in skus.items():
                disp = info.get("disponible", info["stock"] - info["predespacho"])
                if self._sku_state(sku, disp)["nivel"] == "alerta":
                    items.append((sku, info.get("descripcion", ""), alm, disp))
        if not items:
            return

        def build(d, i=0):
            return self._dlg_row([
                ft.Text(d[0], size=11, weight=ft.FontWeight.W_600, width=65),
                ft.Text(d[1][:32], size=11, color=self.c["text_muted"], expand=True),
                ft.Text(d[2], size=11, width=45),
                ft.Text(str(d[3]), size=13, weight=ft.FontWeight.W_700, color=self.c["warning"]),
            ], index=i)

        hdr = [self._dlg_header([("SKU", 65), ("Producto", True), ("Almacén", 45), ("Disp.", None)])]
        sort_cols = [("SKU", lambda x: x[0]), ("Almacén", lambda x: x[2]), ("Disp.", lambda x: x[3])]
        self._show_paginated_dlg("Productos en Alerta (\u2264 5 BX)", hdr, items, build, sort_columns=sort_cols)

    _PAGE_SIZE = 100

    def _next_page(self, title_base, header_rows, data_items, row_builder, page, height,
                   sort_key=None, sort_reverse=False, sort_columns=None):
        # Optimización: En lugar de cerrar, podríamos actualizar el contenido del diálogo.
        # Por ahora, mantenemos la consistencia del framework pero aseguramos limpieza.
        self.page.pop_dialog()
        self._show_paginated_dlg(title_base, header_rows, data_items, row_builder, page, height,
                                  sort_key=sort_key, sort_reverse=sort_reverse, sort_columns=sort_columns)

    def _show_paginated_dlg(self, title_base: str, header_rows: list,
                            data_items: list, row_builder,
                            page: int = 0, height: int = 550,
                            sort_key=None, sort_reverse=False, sort_columns=None):
        try:
            return self._show_paginated_dlg_impl(title_base, header_rows, data_items, row_builder,
                                                  page, height, sort_key, sort_reverse, sort_columns)
        except Exception as ex:
            print(f"[Dialog Error] {ex}")
            import traceback
            traceback.print_exc()

    def _show_paginated_dlg_impl(self, title_base: str, header_rows: list,
                                  data_items: list, row_builder,
                                  page: int = 0, height: int = 550,
                                  sort_key=None, sort_reverse=False, sort_columns=None):
        if sort_columns and sort_key is not None:
            key_fn = None
            for label, fn in sort_columns:
                if label == sort_key:
                    key_fn = fn
                    break
            data_list = sorted(data_items, key=key_fn, reverse=sort_reverse) if key_fn else list(data_items)
        else:
            data_list = list(data_items)

        total = len(data_list)
        start = page * self._PAGE_SIZE
        end = min(start + self._PAGE_SIZE, total)
        data_slice = data_list[start:end]

        total_pages = (total + self._PAGE_SIZE - 1) // self._PAGE_SIZE

        # Sort bar
        sort_bar = []
        if sort_columns:
            sort_controls = []
            for label, fn in sort_columns:
                is_active = label == sort_key
                sort_controls.append(ft.GestureDetector(
                    content=ft.Container(
                        content=ft.Text(label, size=11, weight=ft.FontWeight.W_700 if is_active else ft.FontWeight.W_500,
                                        color="white" if is_active else self.c["text_muted"]),
                        padding=ft.Padding(left=10, right=10, top=4, bottom=4),
                        bgcolor=self.c["accent"] if is_active else rgba(self.c["text_muted"], 0.08),
                        border_radius=14,
                    ),
                    on_tap=lambda e, lb=label: self._next_page(
                        title_base, header_rows, data_items, row_builder, 0, height,
                        sort_key=lb, sort_reverse=(lb == sort_key and not sort_reverse),
                        sort_columns=sort_columns
                    ),
                    mouse_cursor=ft.MouseCursor.CLICK,
                ))
            sort_bar = [ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.SWAP_VERT, size=14, color=self.c["text_muted"]),
                    ft.Text("Orden:", size=10, color=self.c["text_muted"], weight=ft.FontWeight.W_600),
                ] + sort_controls, spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.Padding(left=0, right=0, top=2, bottom=2),
            )]

        # Add sort arrow to header when sorted
        final_headers = list(header_rows)
        if sort_key and sort_columns and final_headers:
            for header_row in final_headers:
                if not hasattr(header_row, 'content') or not hasattr(header_row.content, 'controls'):
                    continue
                try:
                    new_controls = []
                    for ctrl in header_row.content.controls:
                        if isinstance(ctrl, ft.Text):
                            label = ctrl.value
                            is_active = label == sort_key
                            if is_active:
                                icon = ft.Icons.ARROW_UPWARD if not sort_reverse else ft.Icons.ARROW_DOWNWARD
                                new_controls.append(ft.Row([
                                    ctrl,
                                    ft.Icon(icon, size=12, color=self.c["accent"]),
                                ], spacing=2, vertical_alignment=ft.CrossAxisAlignment.CENTER))
                            else:
                                new_controls.append(ctrl)
                        else:
                            new_controls.append(ctrl)
                    header_row.content.controls = new_controls
                except Exception:
                    pass

        export_btn = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.FILE_DOWNLOAD, size=16, color=self.c["accent"]),
                ft.Text("Exportar Excel", size=12, color=self.c["accent"], weight=ft.FontWeight.W_600),
            ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding(left=10, right=10, top=5, bottom=5),
            bgcolor=rgba(self.c["accent"], 0.08),
            border_radius=20,
            on_click=lambda _: self._show_export_config_dlg(title_base, data_list),
        )

        visible = [export_btn] + sort_bar + final_headers + [row_builder(d, i) for i, d in enumerate(data_slice)]

        pagination = []
        nav_spacing = 4

        if page > 0:
            pagination.append(ft.GestureDetector(
                content=ft.Container(
                    content=ft.Row([ft.Text("←", size=12, weight=ft.FontWeight.W_600),
                                    ft.Text("Anterior", size=12, weight=ft.FontWeight.W_500)], spacing=2),
                    padding=ft.Padding(left=10, right=10, top=6, bottom=6),
                    bgcolor=rgba(self.c["text_muted"], 0.06), border_radius=8,
                ),
                on_tap=lambda e, p=page - 1: self._next_page(
                    title_base, header_rows, data_items, row_builder, p, height,
                    sort_key=sort_key, sort_reverse=sort_reverse, sort_columns=sort_columns
                ),
                mouse_cursor=ft.MouseCursor.CLICK,
            ))

        max_visible = 7
        half = max_visible // 2
        p_start = max(0, min(page - half, total_pages - max_visible))
        p_end = min(total_pages, p_start + max_visible)
        for p in range(p_start, p_end):
            is_current = p == page
            pagination.append(ft.GestureDetector(
                content=ft.Container(
                    content=ft.Text(str(p + 1), size=13, weight=ft.FontWeight.W_700 if is_current else ft.FontWeight.W_500,
                                    color="white" if is_current else self.c["text_muted"]),
                    padding=ft.Padding(left=10, right=10, top=6, bottom=6),
                    bgcolor=self.c["accent"] if is_current else rgba(self.c["text_muted"], 0.05),
                    border_radius=8,
                    shadow=ft.BoxShadow(blur_radius=4, color=rgba(self.c["accent"], 0.3)) if is_current else None,
                ),
                on_tap=lambda e, p=p: self._next_page(
                    title_base, header_rows, data_items, row_builder, p, height,
                    sort_key=sort_key, sort_reverse=sort_reverse, sort_columns=sort_columns
                ),
                mouse_cursor=ft.MouseCursor.CLICK,
            ))

        if end < total:
            pagination.append(ft.GestureDetector(
                content=ft.Container(
                    content=ft.Row([ft.Text("Siguientes", size=12, weight=ft.FontWeight.W_500),
                                    ft.Text("→", size=12, weight=ft.FontWeight.W_600)], spacing=2),
                    padding=ft.Padding(left=10, right=10, top=6, bottom=6),
                    bgcolor=rgba(self.c["text_muted"], 0.06), border_radius=8,
                ),
                on_tap=lambda e, p=page + 1: self._next_page(
                    title_base, header_rows, data_items, row_builder, p, height,
                    sort_key=sort_key, sort_reverse=sort_reverse, sort_columns=sort_columns
                ),
                mouse_cursor=ft.MouseCursor.CLICK,
            ))

        pagination_row = ft.Container(
            content=ft.Row(pagination, spacing=nav_spacing, alignment=ft.MainAxisAlignment.CENTER),
            padding=ft.Padding(left=8, right=8, top=8, bottom=6),
        )
        visible.append(pagination_row)

        showing = f"Pág. {page + 1} de {total_pages}" if total_pages > 1 else str(total)
        self._show_dlg(f"{title_base} — {showing}", visible, height)

    def _show_criticos_dlg(self):
        raw = self._get_filtered_raw()
        if not raw or not self._kpis_alm:
            return
        items = []
        for alm, skus in raw.items():
            for sku, info in skus.items():
                disp = info.get("disponible", info["stock"] - info["predespacho"])
                if self._sku_state(sku, disp)["nivel"] == "critico":
                    items.append((sku, info.get("descripcion", ""), alm, disp))
        if not items:
            return

        def build(d, i=0):
            return self._dlg_row([
                ft.Text(d[0], size=11, weight=ft.FontWeight.W_600, width=65),
                ft.Text(d[1][:32], size=11, color=self.c["text_muted"], expand=True),
                ft.Text(d[2], size=11, width=45),
                ft.Text(str(d[3]), size=13, weight=ft.FontWeight.W_700, color=self.c["error"]),
            ], index=i)

        hdr = [self._dlg_header([("SKU", 65), ("Producto", True), ("Almacén", 45), ("Disp.", None)])]
        sort_cols = [("SKU", lambda x: x[0]), ("Almacén", lambda x: x[2]), ("Disp.", lambda x: x[3])]
        self._show_paginated_dlg("Productos Críticos (< 1 BX)", hdr, items, build, sort_columns=sort_cols)

    def _show_sobre_comprometidos_dlg(self):
        raw = self._get_filtered_raw()
        if not raw:
            return
        items = []
        for alm, skus in raw.items():
            for sku, info in skus.items():
                stock = info.get("stock", 0)
                pred = info.get("predespacho", 0)
                if stock > 0 and pred / stock >= 0.85:
                    ratio = round(pred / stock * 100, 1)
                    disp = info.get("disponible", max(0, stock - pred))
                    items.append((sku, info.get("descripcion", ""), alm, pred, disp, ratio))
        if not items:
            return

        def build(d, i=0):
            sku, desc, alm, pred, disp, ratio = d
            st = self._sku_state(sku, disp)
            return self._dlg_row([
                ft.Text(sku, size=11, weight=ft.FontWeight.W_600, width=65),
                ft.Text((desc or "")[:45], size=11, color=self.c["text_muted"], expand=True),
                ft.Text(alm, size=11, width=40),
                ft.Text(f"{pred:,}", size=12, width=55),
                ft.Text(f"{disp:,}", size=13, weight=ft.FontWeight.W_700, width=55, color=st["color"]),
                ft.Text(f"{ratio}%", size=12, width=55, color=rgba("#f97316", 0.9 if ratio >= 99 else 0.7)),
            ], index=i)

        hdr = [self._dlg_header([("SKU", 65), ("Producto", True), ("Almacén", 40), ("Pred.", 55), ("Disp.", 55), ("%", 55)])]
        sort_cols = [("SKU", lambda x: x[0]), ("Pred.", lambda x: x[3]), ("Disp.", lambda x: x[4]), ("%", lambda x: x[5])]
        self._show_paginated_dlg("SKUs ≥85% comprometidos", hdr, items, build, sort_columns=sort_cols)

    def _show_warehouse_skus(self, alm_data: dict):
        cod = alm_data["codigo"]
        stock = self._raw_data.get(cod, {}) if self._raw_data else {}
        raw_skus = sorted(stock.items(), key=lambda x: (
            _sku_info(x[0])["indice"],
            x[1].get("disponible", 0)
        ))
        if not raw_skus:
            return
        raw_skus = [(sku, info) for sku, info in raw_skus if self._match_filtro_sku(sku, info.get("disponible", info["stock"] - info["predespacho"]))]
        if not raw_skus:
            return

        grouped: dict[str, list] = {}
        for sku, info in raw_skus:
            cat = _sku_info(sku)["categoria"]
            grouped.setdefault(cat, []).append((sku, info))

        items = []
        for cat in sorted(grouped, key=lambda c: self._CAT_ORDER.get(c, 9)):
            cat_list = grouped[cat]
            cat_color = self._CAT_COLORS.get(cat, self.c["text_muted"])
            cat_icons = {"VINIBALL": ft.Icons.SPORTS_SOCCER, "VINIFAN": ft.Icons.COLORIZE,
                         "REPRESENTADAS": ft.Icons.BUSINESS, "OTROS": ft.Icons.HELP_OUTLINE}
            items.append(("sep", f"{cat} ({len(cat_list)})", cat_color, cat_icons.get(cat, "")))
            for sku, info in cat_list:
                items.append(("row", sku, info, _sku_info(sku)["indice"]))

        total_pred = sum(info["predespacho"] for _, info in raw_skus)
        total_disp = sum(info.get("disponible", info["stock"] - info["predespacho"]) for _, info in raw_skus)
        summary = self._summary_bar([
            ("SKUs", f"{len(raw_skus)}", self.c["text_primary"]),
            ("Predespacho", f"{total_pred:,}", self.c["warning"]),
            ("Disponible", f"{total_disp:,}", self.c["success"]),
        ])

        data_idx = [0]

        def row_builder(d, _i=0):
            nonlocal data_idx
            if d[0] == "sep":
                return self._dlg_separator(d[1], d[2], d[3])
            sku, info, cat_idx = d[1], d[2], d[3]
            disp = info.get("disponible", info["stock"] - info["predespacho"])
            st = self._sku_state(sku, disp)
            un_bx = _sku_info(sku)["un_bx"]
            bx = info["stock"] // un_bx if un_bx > 0 else info["stock"]
            dbx = disp // un_bx if un_bx > 0 else disp
            idx = data_idx[0]
            data_idx[0] += 1
            dot_color = st["color"]
            dot = ft.Container(width=10, height=10, border_radius=5, bgcolor=dot_color,
                               shadow=ft.BoxShadow(blur_radius=6, color=rgba(dot_color, 0.5)))
            return self._dlg_row([
                ft.Text(str(cat_idx), size=10, color=self.c["text_muted"], width=35),
                ft.Text(sku, size=11, weight=ft.FontWeight.W_600, width=65),
                ft.Text((info.get("descripcion", "") or "")[:45], size=12, color=self.c["text_muted"], expand=True),
                ft.Text(info.get("sku_unit", ""), size=11, width=30, color=self.c["text_muted"]),
                ft.Text(f"{bx:,}", size=12, width=50, color=self.c["text_muted"]),
                ft.Text(f"{info['predespacho']:,}", size=12, width=55, color=rgba(self.c["warning"], 0.8)),
                ft.Text(f"{disp:,}", size=13, weight=ft.FontWeight.W_700, width=60, color=st["color"]),
                ft.Text(f"{dbx:,}", size=12, width=50, color=self.c["text_muted"]),
                dot,
            ], index=idx)

        hdr = [summary, self._dlg_header([("#", 35), ("SKU", 65), ("Producto", True), ("Und", 30), ("BX", 50), ("Pred.", 55), ("Disp.", 60), ("D.BX", 50), ("", 25)])]
        sort_cols = [("#", lambda x: x[3] if x[0]=="row" else 9999), ("SKU", lambda x: x[1] if x[0]=="row" else ""), ("Disp.", lambda x: x[2].get("disponible", 0) if x[0]=="row" else 0)]
        self._show_paginated_dlg(f"{cod} — Detalle SKUs", hdr, items, row_builder, sort_columns=sort_cols)

    def _show_linea_skus(self, linea_cod: str):
        raw = self._get_filtered_raw()
        if not raw:
            return
        seen = set()
        items = []
        for alm, all_skus in raw.items():
            for sku, info in all_skus.items():
                if sku in seen:
                    continue
                seen.add(sku)
                cat_info = _sku_info(sku)
                if cat_info["linea"] == linea_cod:
                    disp = info.get("disponible", info["stock"] - info["predespacho"])
                    if not self._match_filtro_sku(sku, disp):
                        continue
                    items.append((sku, info.get("descripcion", ""), info.get("sku_unit", ""),
                                 info["stock"], info["predespacho"], disp, alm,
                                 cat_info.get("indice", 9999)))

        if not items:
            return
        items.sort(key=lambda x: x[7])  # Orden inicial por índice

        nombre_linea = linea_cod
        for ln in (self._lineas or []):
            if ln["codigo"] == linea_cod:
                nombre_linea = ln.get("nombre", linea_cod)
                break

        def build(d, i=0):
            sku, desc, unit, st, pre, disp, alm, idx = d
            un_bx = _sku_info(sku)["un_bx"]
            bx = st // un_bx if un_bx > 0 else st
            dbx = disp // un_bx if un_bx > 0 else disp
            sc = self._sku_state(sku, disp)
            dot_color = sc["color"]
            dot = ft.Container(width=10, height=10, border_radius=5, bgcolor=dot_color,
                               shadow=ft.BoxShadow(blur_radius=6, color=rgba(dot_color, 0.5)))
            return self._dlg_row([
                ft.Text(str(idx), size=10, color=self.c["text_muted"], width=35),
                ft.Text(sku, size=11, weight=ft.FontWeight.W_600, width=65),
                ft.Text((desc or "")[:45], size=11, color=self.c["text_muted"], expand=True),
                ft.Text(unit, size=11, width=30, color=self.c["text_muted"]),
                ft.Text(f"{bx:,}", size=12, width=50, color=self.c["text_muted"]),
                ft.Text(f"{pre:,}", size=12, width=55, color=rgba(self.c["warning"], 0.8)),
                ft.Text(f"{disp:,}", size=13, weight=ft.FontWeight.W_700, width=60, color=sc["color"]),
                ft.Text(f"{dbx:,}", size=12, width=50, color=self.c["text_muted"]),
                ft.Text(alm, size=11, width=40),
                dot,
            ], index=i)

        hdr = [self._dlg_header([("#", 35), ("SKU", 65), ("Producto", True), ("Und", 30), ("BX", 50), ("Pred.", 55), ("Disp.", 60), ("D.BX", 50), ("Alm", 40), ("", 20)])]
        sort_cols = [("#", lambda x: x[7]), ("SKU", lambda x: x[0]), ("BX", lambda x: x[3]), ("Pred.", lambda x: x[4]),
                     ("Disp.", lambda x: x[5]), ("Alm", lambda x: x[6])]
        self._show_paginated_dlg(f"{nombre_linea} — SKUs", hdr, items, build, sort_columns=sort_cols)

    def _show_sin_linea_dlg(self):
        raw = self._get_filtered_raw()
        if not raw:
            return
        items = []
        for alm, skus in raw.items():
            for sku, info in skus.items():
                if _sku_info(sku)["categoria"] != "OTROS":
                    continue
                disp = info.get("disponible", max(0, info.get("stock", 0) - info.get("predespacho", 0)))
                items.append((sku, info.get("descripcion", ""), alm, info["predespacho"], disp))

        if not items:
            return

        def build(d, i=0):
            sku, desc, alm, pred, disp = d
            st = self._sku_state(sku, disp)
            return self._dlg_row([
                ft.Text(sku, size=11, weight=ft.FontWeight.W_600, width=65),
                ft.Text((desc or "")[:50], size=11, color=self.c["text_muted"], expand=True),
                ft.Text(alm, size=11, width=40, color=self.c["text_muted"]),
                ft.Text(f"{pred:,}", size=12, width=55, color=rgba(self.c["warning"], 0.8)),
                ft.Text(f"{disp:,}", size=13, weight=ft.FontWeight.W_700, width=60, color=st["color"]),
                ft.GestureDetector(
                    content=ft.Icon(ft.Icons.EDIT_SQUARE, size=16, color=rgba(ACCENT, 0.6)),
                    on_tap=lambda e, s=sku, ds=desc: self._show_sku_editor_dlg(s, ds),
                    mouse_cursor=ft.MouseCursor.CLICK,
                ),
            ], index=i)

        hdr = [self._dlg_header([("SKU", 65), ("Producto", True), ("Almacén", 40), ("Pred.", 55), ("Disp.", 60), ("", 30)])]
        sort_cols = [("SKU", lambda x: x[0]), ("Pred.", lambda x: x[3]), ("Disp.", lambda x: x[4])]
        self._show_paginated_dlg(f"SKUs sin categoría ({self._sin_cat_count} total)", hdr, items, build, sort_columns=sort_cols)

    def _show_sku_editor_dlg(self, sku: str, desc: str):
        config = load_lineas()
        lineas_list = config.get("lineas", [])
        linea_options = [ft.dropdown.Option(ln["codigo"], ln.get("nombre", ln["codigo"])) for ln in lineas_list if ln["codigo"] != "SIN LINEA"]

        linea_dd = ft.Dropdown(
            label="Línea", options=linea_options,
            dense=True, width=350, text_size=13,
        )
        cat_dd = ft.Dropdown(
            label="Categoría",
            options=[ft.dropdown.Option(c) for c in ["VINIBALL", "VINIFAN", "REPRESENTADAS"]],
            dense=True, width=350, text_size=13,
        )

        def on_linea_change(e):
            cat = self._LINEA_CAT.get(linea_dd.value, "")
            if cat:
                cat_dd.value = cat
                self.page.update()

        linea_dd.on_change = on_linea_change

        async def on_save(e):
            linea = linea_dd.value
            categoria = cat_dd.value
            if not linea:
                return
            update_catalogo_sku(sku, desc, linea, categoria)
            self.page.pop_dialog()
            self._show_snack(f"SKU {sku} asignado a {linea}")
            self._apply_filters()

        dlg = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.Icons.EDIT_SQUARE, color=ACCENT), ft.Text(f"Editar SKU {sku}", weight=ft.FontWeight.W_800, size=16)]),
            content=ft.Container(content=ft.Column([
                ft.Text(f"Descripción: {desc or '—'}", size=12, color=self.c["text_muted"]),
                ft.Container(height=8),
                linea_dd, cat_dd,
            ], spacing=6, tight=True), width=400),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: self.page.pop_dialog()),
                ft.ElevatedButton("Guardar", bgcolor=ACCENT, color="white", on_click=on_save,
                                  style=ft.ButtonStyle(overlay_color=rgba(ACCENT, 0.1), elevation=0)),
            ],
        )
        self.page.show_dialog(dlg)

    # ─── Dialog Helpers ───

    def _sku_state(self, sku: str, disp: int) -> dict:
        un_bx = _sku_info(sku)["un_bx"]
        if un_bx > 0 and disp < un_bx:
            return {"nivel": "critico", "color": self.c["error"], "emoji": "🔴"}
        if un_bx > 0 and disp <= un_bx * 5:
            return {"nivel": "alerta", "color": self.c["warning"], "emoji": "🟡"}
        return {"nivel": "ok", "color": self.c["success"], "emoji": "🟢"}

    def _match_filtro_sku(self, sku: str, disp: int) -> bool:
        un_bx = _sku_info(sku)["un_bx"]
        if un_bx > 0 and disp < un_bx:
            estado = "critico"
        elif un_bx > 0 and disp <= un_bx * 5:
            estado = "alerta"
        else:
            estado = "ok"
        if self._filtro_salud == "todo":
            return True
        return estado == self._filtro_salud

    _CAT_ORDER = {"VINIBALL": 0, "VINIFAN": 1, "REPRESENTADAS": 2, "OTROS": 3, "SIN LINEA": 4}
    _CAT_COLORS = {
        "VINIBALL": ACCENT,
        "VINIFAN": "#3b82f6",
        "REPRESENTADAS": "#8b5cf6",
        "OTROS": "#6b7280",
    }
    _LINEA_CAT = {
        "PELOTAS": "VINIBALL", "MASCOTAS": "VINIBALL",
        "ACCESORIOS": "VINIFAN", "ARCHIVO": "VINIFAN", "DIBUJO": "VINIFAN",
        "DIDACTICOS": "VINIFAN", "ESCRITURA": "VINIFAN", "FORROS": "VINIFAN",
        "MANUALIDADES": "VINIFAN", "METALICA": "VINIFAN", "PEGAMENTOS": "VINIFAN",
        "PINTURA": "VINIFAN", "REPRESENTADAS": "REPRESENTADAS",
    }

    def _dlg_header(self, columns: list[tuple]) -> ft.Container:
        controls = []
        for label, width in columns:
            if width is True:
                controls.append(ft.Text(label, size=11, weight=ft.FontWeight.W_700, color=self.c["accent"], expand=True))
            elif width is None:
                controls.append(ft.Text(label, size=11, weight=ft.FontWeight.W_700, color=self.c["accent"]))
            else:
                controls.append(ft.Text(label, size=11, weight=ft.FontWeight.W_700, color=self.c["accent"], width=width))
        return ft.Container(
            content=ft.Row(controls, spacing=6),
            bgcolor=rgba(self.c["accent"], 0.12), border_radius=6,
            padding=ft.Padding(left=8, right=8, top=6, bottom=6),
        )

    def _dlg_row(self, controls: list, index: int = 0) -> ft.Container:
        bg = rgba(self.c["accent"], 0.03) if index % 2 == 1 else "transparent"
        return ft.Container(
            content=ft.Row(controls, spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=bg, padding=ft.Padding(left=8, right=8, top=5, bottom=5),
        )

    def _dlg_separator(self, text: str, color: str, icon: str = "") -> ft.Container:
        return ft.Container(
            content=ft.Row([
                ft.Icon(icon, size=14, color=color) if icon else ft.Container(width=0),
                ft.Text(text, size=13, weight=ft.FontWeight.W_700, color=color),
            ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=rgba(color, 0.08),
            border_radius=6,
            padding=ft.Padding(left=10, right=10, top=6, bottom=6),
        )

    def _summary_bar(self, items: list[tuple[str, str, str]]) -> ft.Container:
        cells = []
        for label, value, color in items:
            cells.append(ft.Column([
                ft.Text(label, size=10, color=self.c["text_muted"], weight=ft.FontWeight.W_500),
                ft.Text(value, size=14, weight=ft.FontWeight.W_800, color=color),
            ], spacing=1, horizontal_alignment=ft.CrossAxisAlignment.CENTER))
        return ft.Container(
            content=ft.Row(cells, spacing=24, alignment=ft.MainAxisAlignment.CENTER),
            bgcolor=rgba(ACCENT, 0.05), border_radius=8,
            padding=ft.Padding(left=12, right=12, top=8, bottom=8),
        )

    def _show_dlg(self, title: str, rows: list, height: int):
        dlg = ft.AlertDialog(
            title=ft.Text(title, weight=ft.FontWeight.W_800, size=16, color=self.c["text_primary"]),
            content=ft.Container(ft.Column(rows, spacing=0, scroll=ft.ScrollMode.AUTO), width=760, height=height),
            actions=[ft.TextButton("Cerrar", on_click=lambda e: self.page.pop_dialog())],
        )
        self.page.show_dialog(dlg)

    def _close_dlg(self, dlg):
        self.page.pop_dialog()

    def update_data(self, raw_data: dict[str, dict[str, dict]]):
        self._raw_data = raw_data
        config = load_lineas()
        alm_config = config.get("almacenes", {})
        self._selected_alms = set()
        for cod, cfg in alm_config.items():
            if cfg.get("rol", "") in ("PRINCIPAL", "SECUNDARIO"):
                self._selected_alms.add(cod)
        if not self._selected_alms:
            self._selected_alms = set(raw_data.keys())

        sort_order = {"PRINCIPAL": 0, "SECUNDARIO": 1, "EXTERNO": 2}
        sorted_codes = sorted(raw_data.keys(), key=lambda c: (sort_order.get(alm_config.get(c, {}).get("rol", ""), 9), alm_config.get(c, {}).get("prioridad", 99)))
        chips = []
        self._chip_refs: dict[str, ft.GestureDetector] = {}
        for cod in sorted_codes:
            rol = alm_config.get(cod, {}).get("rol", "")
            selected = cod in self._selected_alms
            chip = self._sidebar_chip(cod, rol, selected)
            self._chip_refs[cod] = chip
            chips.append(chip)
        self._sidebar_chips.controls = chips
        self._apply_filters()

    def _show_export_config_dlg(self, title: str, data: list):
        alms_in_data = sorted(list(set(d[6] if (isinstance(d, (list, tuple)) and len(d) > 6) else "VES" for d in data)))
        mode_radio = ft.RadioGroup(content=ft.Column([
            ft.Radio(value="basic", label="Básico (Solo Disponibilidad)"),
            ft.Radio(value="detailed", label="Completo (Stock + Predespacho)"),
        ]), value="basic")
        summary_check = ft.Checkbox(label="Incluir pestaña de Resumen consolidado", value=True)
        alm_dropdown = ft.Dropdown(
            label="Filtrar Almacén",
            options=[ft.dropdown.Option("TODOS", "Todos los de la vista")] + [ft.dropdown.Option(a) for a in alms_in_data],
            value="TODOS",
            dense=True,
        )

        async def on_confirm(_):
            detailed = mode_radio.value == "detailed"
            target_alm = alm_dropdown.value
            export_data = data
            if target_alm != "TODOS":
                export_data = [d for d in data if (isinstance(d, (list, tuple)) and len(d) > 6 and d[6] == target_alm)]
            
            export_title = title if target_alm == "TODOS" else f"{title}_{target_alm}"
            self.page.pop_dialog()
            path = await self._file_picker.save_file(file_name=f"{export_title.replace(' ', '_')}.xlsx")
            if path:
                try:
                    export_to_excel(
                        export_data, path, export_title,
                        detailed, summary_check.value
                    )
                    self._show_snack("Archivo Excel generado con éxito")
                    import os
                    os.startfile(path)
                except Exception as ex:
                    self._show_snack(f"Error al exportar: {ex}", is_error=True)

        dlg = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.Icons.SETTINGS_SUGGEST, color=ACCENT), ft.Text("Configurar Exportación", weight=ft.FontWeight.W_800, size=16)]),
            content=ft.Container(content=ft.Column([
                ft.Container(
                    content=ft.Column([mode_radio, summary_check, alm_dropdown], spacing=8),
                    padding=10,
                ),
            ], spacing=5, tight=True), width=420),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: self.page.pop_dialog()),
                ft.ElevatedButton("Generar Archivo", bgcolor=ACCENT, color="white", on_click=on_confirm,
                                  style=ft.ButtonStyle(overlay_color=rgba(ACCENT, 0.1), elevation=0)),
            ],
        )
        self.page.show_dialog(dlg)


