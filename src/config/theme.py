import json
from pathlib import Path

ACCENT = "#10B981"
ACCENT_DARK = "#047857"
EMERALD_LIGHT = "#34d399"
EMERALD_DARK = "#059669"

SUCCESS = "#34d399"
WARNING = "#f59e0b"
ERROR = "#ef4444"
INFO = "#3b82f6"
VIOLET = "#8b5cf6"
PINK = "#ec4899"
CYAN = "#06b6d4"

DARK_COLORS = {
    "accent": ACCENT,
    "accent_dark": ACCENT_DARK,
    "success": SUCCESS,
    "warning": WARNING,
    "error": ERROR,
    "info": INFO,
    "violet": VIOLET,
    "pink": PINK,
    "cyan": CYAN,
    "surface": "#1a2333",
    "surface_variant": "#243044",
    "background": "#0b1220",
    "border": "#ffffff12",
    "text_muted": "#94a3b8",
    "text_primary": "#f0f4f8",
    "text_secondary": "#cbd5e1",
}

LIGHT_COLORS = {
    "accent": ACCENT,
    "accent_dark": ACCENT_DARK,
    "success": SUCCESS,
    "warning": WARNING,
    "error": ERROR,
    "info": INFO,
    "violet": VIOLET,
    "pink": PINK,
    "cyan": CYAN,
    "surface": "#ffffff",           # Fondo de tarjetas/componentes
    "surface_variant": "#f8fafc",   # Variación ligera para hover o secciones
    "background": "#f1f5f9",        # Fondo principal de la página
    "border": "#e2e8f0",            # Bordes más visibles en tema claro
    "text_muted": "#64748b",        # Texto gris para detalles
    "text_primary": "#0f172a",      # Texto casi negro para máxima legibilidad
    "text_secondary": "#334155",    # Texto gris oscuro
}


def get_colors(mode: str) -> dict:
    return dict(DARK_COLORS if mode == "dark" else LIGHT_COLORS)


def rgba(color: str, opacity: float) -> str:
    hex_color = color[1:] if color.startswith("#") else color
    if len(hex_color) == 6:
        alpha = int(opacity * 255)
        return f"#{alpha:02x}{hex_color}"
    return color


def get_theme_file() -> Path:
    return Path.home() / ".g360" / "stock_monitor_config.json"


def load_theme_preference() -> str:
    try:
        config_file = get_theme_file()
        if config_file.exists():
            with open(config_file, encoding="utf-8") as f:
                config = json.load(f)
                return config.get("theme_mode", "dark")
    except Exception:
        pass
    return "dark"


def save_theme_preference(mode: str):
    try:
        config_file = get_theme_file()
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config = {"theme_mode": mode}
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f)
    except Exception:
        pass


WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
WINDOW_MIN_WIDTH = 900
WINDOW_MIN_HEIGHT = 600
