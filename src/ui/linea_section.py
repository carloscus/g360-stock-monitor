from __future__ import annotations

import flet as ft
from src.config.theme import rgba
from src.core.constants import PRIMARY_CATEGORIES

_CAT_ICONS = {
    "VINIBALL": ft.Icons.SPORTS_SOCCER,
    "VINIFAN": ft.Icons.COLORIZE,
    "REPRESENTADAS": ft.Icons.BUSINESS,
}


class LineaSection:
    def __init__(self, lineas: list[dict], categorias: list[dict], colors: dict,
                 on_linea_click=None, filtro_salud: str = "todo",
                 lineas_sin_catalogo: list[dict] | None = None,
                 categorias_sin_catalogo: list[dict] | None = None):
        self.lineas = lineas
        self.categorias = categorias
        self.c = colors
        self.on_linea_click = on_linea_click
        self.filtro_salud = filtro_salud
        self.lineas_sin_catalogo = lineas_sin_catalogo or []
        self.categorias_sin_catalogo = categorias_sin_catalogo or []

    def build(self) -> ft.Container:
        cat_sections = []
        otras_cats = []
        sin_catalogo_sections = []

        for cat in self.categorias:
            ctg = cat["categoria"]
            icon = _CAT_ICONS.get(ctg, ft.Icons.CATEGORY)
            lines_in_cat = [ln for ln in self.lineas if ln.get("categoria", "").upper() == ctg.upper()]
            if ctg in PRIMARY_CATEGORIES:
                if lines_in_cat:
                    cat_sections.append(self._cat_card(ctg, icon, cat, lines_in_cat))
            else:
                otras_cats.append((ctg, icon, cat, lines_in_cat))

        for cat in self.categorias_sin_catalogo:
            ctg = cat["categoria"]
            icon = _CAT_ICONS.get(ctg, ft.Icons.CATEGORY)
            orphan_lines = [ln for ln in self.lineas_sin_catalogo if ln.get("categoria", "").upper() == ctg.upper()]
            if orphan_lines:
                sin_catalogo_sections.append(self._sin_catalogo_card(ctg, icon, cat, orphan_lines))

        if otras_cats:
            cat_sections.append(self._otras_card(otras_cats))

        if sin_catalogo_sections:
            cat_sections.append(self._sin_catalogo_section(sin_catalogo_sections))

        if not cat_sections:
            for linea in self.lineas[:5]:
                cat_sections.append(self._linea_card(linea))

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Categorías", size=16, weight=ft.FontWeight.W_700, color=self.c["text_primary"]),
                    ft.Container(expand=True),
                    ft.Text(f"{len(self.categorias)} categorías • {len(self.lineas)} líneas",
                            size=11, color=self.c["text_muted"]),
                ]),
                ft.Container(height=10),
                ft.Column(cat_sections, spacing=12),
            ]),
            padding=20,
        )

    def _otras_card(self, cats: list[tuple[str, str, dict, list[dict]]]) -> ft.Container:
        sections = []
        for ctg, icon, cat_data, lines_in_cat in cats:
            if not lines_in_cat:
                continue
            sections.append(ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Container(
                            content=ft.Icon(icon, size=15, color="white"),
                            bgcolor=rgba(self.c["text_muted"], 0.15), border_radius=6, padding=6,
                        ),
                        ft.Text(ctg, size=13, weight=ft.FontWeight.W_700, color=self.c["text_primary"]),
                        ft.Container(expand=True),
                        ft.Text(f"{cat_data.get('disponible', 0):,} disp.",
                                size=12, weight=ft.FontWeight.W_700, color=self.c["success"]),
                    ], spacing=10),
                    *[self._linea_card(ln) for ln in lines_in_cat[:10]],
                ], spacing=6),
                padding=12,
            ))

        total_disp = sum(c[2].get("disponible", 0) for c in cats)
        total_lines = sum(len(c[3]) for c in cats)

        return ft.Container(
            content=ft.ExpansionTile(
                title=ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.Icons.APPS, size=16, color="white"),
                        bgcolor=rgba(self.c["accent"], 0.15), border_radius=8, padding=7,
                    ),
                    ft.Text("OTRAS CATEGORÍAS", size=14, weight=ft.FontWeight.W_700, color=self.c["text_primary"]),
                ], spacing=10),
                subtitle=ft.Text(f"{len(cats)} categorías • {total_lines} líneas",
                                 size=11, color=self.c["text_muted"]),
                trailing=ft.Container(
                    content=ft.Text(f"{total_disp:,} disp.", size=12, weight=ft.FontWeight.W_700,
                                    color=self.c["success"]),
                ),
                controls=sections,
                initially_expanded=True,
                bgcolor=rgba(self.c["accent"], 0.03),
                collapsed_bgcolor=rgba(self.c["accent"], 0.03),
                tile_padding=ft.Padding(left=16, right=16, top=10, bottom=10),
                controls_padding=ft.Padding(left=16, right=16, top=0, bottom=10),
                shape=ft.RoundedRectangleBorder(radius=12),
                collapsed_shape=ft.RoundedRectangleBorder(radius=12),
            ),
            border=ft.Border(
                top=ft.BorderSide(1, rgba(self.c["accent"], 0.08)),
                right=ft.BorderSide(1, rgba(self.c["accent"], 0.08)),
                bottom=ft.BorderSide(1, rgba(self.c["accent"], 0.08)),
                left=ft.BorderSide(1, rgba(self.c["accent"], 0.08)),
            ),
            border_radius=12,
        )

    def _sin_catalogo_card(self, name: str, icon: str, cat_data: dict, lines: list[dict]) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Icon(icon, size=15, color="white"),
                        bgcolor=rgba(self.c["warning"], 0.25), border_radius=6, padding=6,
                    ),
                    ft.Text(f"Sin catálogo — {name}", size=13, weight=ft.FontWeight.W_700, color=self.c["text_primary"]),
                    ft.Container(expand=True),
                    ft.Text(f"{cat_data.get('disponible', 0):,} disp.",
                            size=12, weight=ft.FontWeight.W_700, color=self.c["warning"]),
                ], spacing=10),
                *[self._linea_card(ln) for ln in lines[:10]],
            ], spacing=6),
            padding=12,
        )

    def _sin_catalogo_section(self, sections: list[ft.Container]) -> ft.Container:
        return ft.Container(
            content=ft.ExpansionTile(
                title=ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.Icons.INVENTORY_2, size=16, color="white"),
                        bgcolor=rgba(self.c["warning"], 0.25), border_radius=8, padding=7,
                    ),
                    ft.Text("SIN CATÁLOGO", size=14, weight=ft.FontWeight.W_700, color=self.c["text_primary"]),
                ], spacing=10),
                subtitle=ft.Text(f"{len(sections)} categorías con productos no vigentes",
                                 size=11, color=self.c["text_muted"]),
                controls=sections,
                initially_expanded=False,
                bgcolor=rgba(self.c["warning"], 0.03),
                collapsed_bgcolor=rgba(self.c["warning"], 0.03),
                tile_padding=ft.Padding(left=16, right=16, top=10, bottom=10),
                controls_padding=ft.Padding(left=16, right=16, top=0, bottom=10),
                shape=ft.RoundedRectangleBorder(radius=12),
                collapsed_shape=ft.RoundedRectangleBorder(radius=12),
            ),
            border=ft.Border(
                top=ft.BorderSide(1, rgba(self.c["warning"], 0.12)),
                right=ft.BorderSide(1, rgba(self.c["warning"], 0.12)),
                bottom=ft.BorderSide(1, rgba(self.c["warning"], 0.12)),
                left=ft.BorderSide(1, rgba(self.c["warning"], 0.12)),
            ),
            border_radius=12,
        )

    def _cat_card(self, name: str, icon: str, cat_data: dict, lines: list[dict]) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Icon(icon, size=18, color="white"),
                        bgcolor=rgba(self.c["accent"], 0.15), border_radius=8, padding=8,
                    ),
                    ft.Text(name, size=15, weight=ft.FontWeight.W_700, color=self.c["text_primary"]),
                    ft.Container(expand=True),
                    ft.Text(f"{cat_data.get('disponible', 0):,} disp.",
                            size=13, weight=ft.FontWeight.W_700, color=self.c["success"]),
                ], spacing=10),
                *[self._linea_card(ln) for ln in lines[:10]],
            ], spacing=6),
            bgcolor=rgba(self.c["accent"], 0.03), border_radius=12,
            border=ft.Border(top=ft.BorderSide(1, rgba(self.c["accent"], 0.08)), right=ft.BorderSide(1, rgba(self.c["accent"], 0.08)), bottom=ft.BorderSide(1, rgba(self.c["accent"], 0.08)), left=ft.BorderSide(1, rgba(self.c["accent"], 0.08))),
            padding=16,
        )

    def _linea_card(self, linea: dict) -> ft.GestureDetector:
        stock = linea.get("stock", 0)
        disp = linea.get("disponible", stock)
        skus = linea.get("skus", 0)
        cod = linea["codigo"]
        nombre = linea.get("nombre", cod)
        sv = linea.get("stock_ves", 0)
        sq = linea.get("stock_qc", 0)
        ss = linea.get("stock_secundario", 0)
        sm = linea.get("stock_minimo", 0)
        salud = linea.get("salud", "bueno")
        pct = linea.get("pct_minimo", 100)
        estado_linea = str(linea.get("estado_linea", "")).strip()

        salud_color = {"critico": self.c["error"], "alerta": self.c["warning"], "bueno": self.c["success"]}
        salud_icon = {"critico": "🔴", "alerta": "🟡", "bueno": "🟢"}
        sc = salud_color.get(salud, self.c["success"])

        estado_badge = None
        if estado_linea:
            estado_color = {
                "nuevo": self.c["accent"],
                "nacional": "#3b82f6",
                "importado": "#8b5cf6",
                "tradicional": "#f59e0b",
            }.get(estado_linea.lower(), self.c["text_muted"])
            estado_badge = ft.Container(
                content=ft.Text(estado_linea.upper(), size=9, color="white", weight=ft.FontWeight.W_700),
                bgcolor=estado_color, border_radius=4, padding=ft.Padding(left=6, right=6, top=2, bottom=2),
            )

        health_pct = min(pct, 100)

        inner = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(f"{salud_icon.get(salud, '')} {nombre}", size=13, weight=ft.FontWeight.W_600,
                            color=self.c["text_primary"], expand=True),
                    estado_badge if estado_badge else ft.Container(),
                    ft.Text(f"{skus} SKUs", size=11, color=self.c["text_muted"]),
                    ft.Text(f"S:{stock:,}", size=11, color=self.c["text_muted"]),
                    ft.Text(f"D:{disp:,}", size=12, weight=ft.FontWeight.W_700, color=self.c["success"]),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, size=16, color=self.c["text_muted"]),
                ], spacing=8),
                ft.Row([
                    ft.Text("VES:", size=10, color=sc, weight=ft.FontWeight.W_600),
                    ft.Text(f"{sv:,}", size=11, color=self.c["text_primary"]),
                    ft.Text(f"| QC: {sq:,}", size=10, color=self.c["text_muted"]),
                    ft.Text(f"| Sec: {ss:,}", size=10, color=self.c["text_muted"]),
                    ft.Container(expand=True),
                    ft.Text(f"mín {sm:,}", size=10, color=self.c["text_muted"]),
                ], spacing=6),
                ft.Stack([
                    ft.Container(height=5, bgcolor=rgba(self.c["text_muted"], 0.2), border_radius=2),
                    ft.Container(height=5, width=max(health_pct, 0) * 3, bgcolor=sc, border_radius=2),
                ]),
            ], spacing=4),
            padding=ft.Padding(left=12, right=12, top=10, bottom=10),
            bgcolor=rgba(self.c["accent"], 0.02), border_radius=8,
            tooltip=f"Ver SKUs de {nombre}",
        )
        return ft.GestureDetector(
            content=inner,
            on_tap=lambda e, c=cod: self._on_linea_click(c),
            mouse_cursor=ft.MouseCursor.CLICK,
        )

    def _on_linea_click(self, linea_cod: str):
        if self.on_linea_click:
            self.on_linea_click(linea_cod)
