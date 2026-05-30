from __future__ import annotations

import flet as ft
from src.config.theme import rgba, ACCENT


class LineaSection:
    def __init__(self, lineas: list[dict], categorias: list[dict], colors: dict,
                 on_linea_click=None, sin_linea: int = 0, filtro_salud: str = "todo"):
        self.lineas = lineas
        self.categorias = categorias
        self.c = colors
        self.on_linea_click = on_linea_click
        self.sin_linea = sin_linea
        self.filtro_salud = filtro_salud

    def build(self) -> ft.Container:
        cat_icons = {
            "VINIBALL": ft.Icons.SPORTS_SOCCER,
            "VINIFAN": ft.Icons.COLORIZE,
            "REPRESENTADAS": ft.Icons.BUSINESS,
        }
        cat_sections = []
        for cat in self.categorias:
            ctg = cat["categoria"]
            icon = cat_icons.get(ctg, ft.Icons.CATEGORY)
            lines_in_cat = [ln for ln in self.lineas if ln.get("categoria", "").upper() == ctg.upper()]
            if not lines_in_cat:
                continue
            cat_sections.append(self._cat_card(ctg, icon, cat, lines_in_cat))

        footer = []
        if self.sin_linea:
            footer.append(ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.HELP_OUTLINE, size=12, color=self.c["text_muted"]),
                    ft.Text(f"{self.sin_linea} SKUs sin categoría en el catálogo", size=10, color=self.c["text_muted"]),
                ], spacing=4),
                margin=ft.Margin(top=4, bottom=0, left=0, right=0),
            ))

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
                *footer,
            ]),
            padding=20,
        )

    def _cat_card(self, name: str, icon: str, cat_data: dict, lines: list[dict]) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Icon(icon, size=18, color="white"),
                        bgcolor=rgba(ACCENT, 0.15), border_radius=8, padding=8,
                    ),
                    ft.Text(name, size=15, weight=ft.FontWeight.W_700, color=self.c["text_primary"]),
                    ft.Container(expand=True),
                    ft.Text(f"{cat_data.get('disponible', 0):,} disp.",
                            size=13, weight=ft.FontWeight.W_700, color=self.c["success"]),
                ], spacing=10),
                *[self._linea_card(ln) for ln in lines[:10]],
            ], spacing=6),
            bgcolor=rgba(ACCENT, 0.03), border_radius=12,
            border=ft.Border(top=ft.BorderSide(1, rgba(ACCENT, 0.08)), right=ft.BorderSide(1, rgba(ACCENT, 0.08)), bottom=ft.BorderSide(1, rgba(ACCENT, 0.08)), left=ft.BorderSide(1, rgba(ACCENT, 0.08))),
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

        salud_color = {"critico": self.c["error"], "alerta": self.c["warning"], "bueno": self.c["success"]}
        salud_icon = {"critico": "🔴", "alerta": "🟡", "bueno": "🟢"}
        sc = salud_color.get(salud, self.c["success"])

        health_pct = min(pct, 100)

        inner = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(f"{salud_icon.get(salud, '')} {nombre}", size=13, weight=ft.FontWeight.W_600,
                            color=self.c["text_primary"], expand=True),
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
            bgcolor=rgba(ACCENT, 0.02), border_radius=8,
        )
        return ft.GestureDetector(
            content=inner,
            on_tap=lambda e, c=cod: self._on_linea_click(c),
            mouse_cursor=ft.MouseCursor.CLICK,
            tooltip=f"Ver SKUs de {nombre}",
        )

    def _on_linea_click(self, linea_cod: str):
        if self.on_linea_click:
            self.on_linea_click(linea_cod)
