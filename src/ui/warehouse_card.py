from __future__ import annotations

import flet as ft
from src.config.theme import rgba


class WarehouseCard:
    def __init__(self, data: dict, config: dict, colors: dict, on_click=None):
        self.data = data
        self.cfg = config
        self.c = colors
        self.on_click = on_click

    def build(self) -> ft.Container:
        d = self.data
        cod = d["codigo"]
        tipo = (self.cfg.get("tipo_reporte") or "").upper()
        rol = (self.cfg.get("rol") or "").upper()
        part_control = self.cfg.get("participa_control", False)
        nombre_real = self.cfg.get("nombre", cod)

        cambio = d.get("cambio")
        trend = None
        if cambio:
            if cambio["absoluto"] > 0:
                trend = (ft.Icons.TRENDING_UP, self.c["success"], f"+{cambio['porcentaje']}%")
            elif cambio["absoluto"] < 0:
                trend = (ft.Icons.TRENDING_DOWN, self.c["error"], f"{cambio['porcentaje']}%")
            else:
                trend = (ft.Icons.REMOVE, self.c["text_muted"], "0%")

        rol_badge = None
        if rol == "PRINCIPAL":
            rol_badge = ft.Container(
                content=ft.Text("PRINCIPAL", size=10, color="white", weight=ft.FontWeight.W_700),
                bgcolor=self.c["accent"], border_radius=5, padding=ft.Padding(left=8, right=8, top=3, bottom=3),
            )
        elif rol == "SECUNDARIO":
            rol_badge = ft.Container(
                content=ft.Text("SECUNDARIO", size=10, color="white", weight=ft.FontWeight.W_700),
                bgcolor=rgba(self.c["info"], 0.9), border_radius=5, padding=ft.Padding(left=8, right=8, top=3, bottom=3),
            )

        # Metricas horizontales segun tipo de reporte
        metrics_content = []
        if tipo == "DESAGREGADO":
            ratio = 0
            denom = d["predespacho_total"] + d["disponible_total"]
            if denom > 0:
                ratio = d["predespacho_total"] / denom * 100
            
            metrics_content = [
                self._metric_item("Stock", f"{d['stock_total']:,}", self.c["text_primary"]),
                self._metric_item("Pred.", f"{d['predespacho_total']:,}", self.c["warning"]),
                self._mini_ratio(ratio),
                self._metric_item("Disp.", f"{d['disponible_total']:,}", self.c["success"]),
                self._metric_item("D.BX", f"{d.get('disponible_bx', 0):,}", self.c["success"]),
            ]
        elif tipo == "CONSOLIDADO":
            metrics_content = [
                self._metric_item("Stock", f"{d['stock_total']:,}", self.c["text_primary"]),
                self._metric_item("Disp.", f"{d['disponible_total']:,}", self.c["success"]),
            ]
        else: # Tipo PCT
            total = d["disponible_total"] + d["predespacho_total"]
            metrics_content = [
                self._metric_item("Info Stock", f"{d['disponible_total']} de {total}", self.c["text_muted"]),
            ]

        return ft.Container(
            content=ft.Row([
                # 1. Identidad (Izquierda)
                ft.Column([
                    ft.Row([
                        ft.Text(cod, size=18, weight=ft.FontWeight.W_800, color=self.c["text_primary"]),
                        rol_badge if rol_badge else ft.Container(),
                    ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Text(nombre_real, size=13, color=self.c["text_muted"], max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, tooltip=nombre_real),
                ], spacing=3, expand=2),

                # 2. Métricas (Centro)
                ft.Row(metrics_content, spacing=28, expand=4, alignment=ft.MainAxisAlignment.CENTER),

                # 3. Estado y Tendencia (Derecha)
                ft.Row([
                    ft.Row([
                        self._status_dot(str(d["criticos"]), self.c["error"]) if part_control and d["criticos"] > 0 else ft.Container(),
                        self._status_dot(str(d["alertas"]), self.c["warning"]) if part_control and d["alertas"] > 0 else ft.Container(),
                    ], spacing=6),
                    ft.VerticalDivider(width=1, color=self.c["border"]),
                    ft.Column([
                        ft.Icon(trend[0], color=trend[1], size=18) if trend else ft.Container(),
                        ft.Text(trend[2], size=11, color=trend[1], weight=ft.FontWeight.BOLD) if trend else ft.Container(),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                ], spacing=14, alignment=ft.MainAxisAlignment.END, expand=2),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.Padding(left=24, right=24, top=14, bottom=14),
            bgcolor=self.c["surface"],
            border_radius=10,
            border=ft.Border(bottom=ft.BorderSide(1, self.c["border"])),
            tooltip="Ver detalle de SKUs",
            on_click=lambda _: self.on_click(d) if self.on_click else None,
            ink=True,
        )

    def _metric_item(self, label: str, value: str, color: str):
        return ft.Column([
            ft.Text(label, size=10, color=self.c["text_muted"], weight=ft.FontWeight.W_500),
            ft.Text(value, size=15, color=color, weight=ft.FontWeight.W_700),
        ], spacing=1, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def _mini_ratio(self, value: float):
        return ft.Column([
            ft.Text("Ratio", size=9, color=self.c["text_muted"]),
            ft.Container(
                content=ft.ProgressBar(value=value/100, color=self.c["accent"], bgcolor=rgba(self.c["accent"], 0.12), height=4),
                width=60, border_radius=2
            ),
        ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def _status_dot(self, count: str, color: str):
        return ft.Container(
            content=ft.Text(count, size=11, color="white", weight=ft.FontWeight.W_700),
            bgcolor=color, border_radius=6, padding=ft.Padding(left=8, right=8, top=3, bottom=3),
        )

    def update_theme(self, colors: dict):
        """Actualiza colores in-place sin reconstruir la card."""
        self.c = colors
        main = self._main_container
        if not main:
            return
        main.bgcolor = colors["surface"]
        main.border = ft.Border(bottom=ft.BorderSide(1, colors["border"]))
        row = main.content
        # Left: identity column
        left_col = row.controls[0]
        if isinstance(left_col, ft.Column):
            id_row = left_col.controls[0]
            if isinstance(id_row, ft.Row):
                cod_text = id_row.controls[0]
                if isinstance(cod_text, ft.Text):
                    cod_text.color = colors["text_primary"]
                badge = id_row.controls[1] if len(id_row.controls) > 1 else None
                if isinstance(badge, ft.Container) and isinstance(badge.content, ft.Text):
                    badge.bgcolor = colors["accent"] if badge.content.value == "PRINCIPAL" else (rgba(colors["info"], 0.9) if badge.content.value == "SECUNDARIO" else "transparent")
            name_text = left_col.controls[1] if len(left_col.controls) > 1 else None
            if isinstance(name_text, ft.Text):
                name_text.color = colors["text_muted"]
        # Middle: metrics
        mid_row = row.controls[1]
        if isinstance(mid_row, ft.Row):
            for mc in mid_row.controls:
                if isinstance(mc, ft.Column) and len(mc.controls) >= 2:
                    mc.controls[0].color = colors["text_muted"]
                elif isinstance(mc, ft.Container):
                    inner = mc.content
                    if isinstance(inner, ft.Column) and len(inner.controls) >= 2:
                        inner.controls[0].color = colors["text_muted"]
                        if len(inner.controls) > 2:
                            pr = inner.controls[2].content
                            if isinstance(pr, ft.ProgressBar):
                                pr.color = colors["accent"]
                                pr.bgcolor = rgba(colors["accent"], 0.12)
        # Right: status + trend
        right_col = row.controls[2]
        if isinstance(right_col, ft.Row):
            inner = right_col.controls
            if len(inner) > 1 and isinstance(inner[1], ft.VerticalDivider):
                inner[1].color = colors["border"]
            if len(inner) > 2:
                trend_col = inner[2]
                if isinstance(trend_col, ft.Column):
                    for tc in trend_col.controls:
                        if isinstance(tc, ft.Icon):
                            pass
                        elif isinstance(tc, ft.Text):
                            v = tc.value
                            tc.color = colors["success"] if v.startswith("+") else (colors["error"] if v.endswith("%") and not v.startswith("+") else (colors["text_muted"] if v == "0%" else tc.color))