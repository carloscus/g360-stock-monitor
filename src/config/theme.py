import json
from pathlib import Path

ACCENT = "#10B981"
ACCENT_DARK = "#047857"

DARK_COLORS = {
    "accent": "#10B981",
    "accent_dark": "#047857",
    "success": "#34D399",
    "warning": "#F59E0B",
    "error": "#EF4444",
    "info": "#3B82F6",
    "violet": "#8B5CF6",
    "pink": "#EC4899",
    "cyan": "#06B6D4",
    "orange": "#F97316",
    "kpis": {
        "almacenes": "#06B6D4",      # cyan
        "skus": "#8B5CF6",           # violet
        "disponible": "#0EA5E9",     # sky blue
        "predespacho": "#6366F1",    # indigo
        "sin_catalogo": "#EC4899",   # pink
        "alertas": "#F59E0B",        # amber
        "criticos": "#EF4444",       # red
        "alto_stock": "#F97316",     # orange
    },
    "surface": "#141D33",
    "surface_variant": "#1B2740",
    "surface_sunken": "#0E1627",
    "background": "#0A0F1E",
    "border": "#FFFFFF17",
    "text_muted": "#8FA0BA",
    "text_primary": "#F1F5FB",
    "text_secondary": "#C9D4E6",
}

LIGHT_COLORS = {
    "accent": "#047857",
    "accent_dark": "#065F46",
    "success": "#15803D",
    "warning": "#B45309",
    "error": "#DC2626",
    "info": "#2563EB",
    "violet": "#7C3AED",
    "pink": "#DB2777",
    "cyan": "#0891B2",
    "orange": "#EA580C",
    "kpis": {
        "almacenes": "#0891B2",      # cyan
        "skus": "#7C3AED",           # violet
        "disponible": "#0284C7",     # sky blue
        "predespacho": "#4F46E5",    # indigo
        "sin_catalogo": "#DB2777",   # pink
        "alertas": "#B45309",        # amber
        "criticos": "#DC2626",       # red
        "alto_stock": "#EA580C",     # orange
    },
    "surface": "#FFFFFF",
    "surface_variant": "#F7F9FC",
    "surface_sunken": "#EEF1F6",
    "background": "#F3F5F9",
    "border": "#E3E8F0",
    "text_muted": "#64748B",
    "text_primary": "#0F172A",
    "text_secondary": "#334155",
}


def get_colors(mode: str) -> dict:
    return dict(DARK_COLORS if mode == "dark" else LIGHT_COLORS)


def rgba(color: str, opacity: float) -> str:
    if color.startswith("#") and len(color) == 9:
        return color  # already has alpha
    if color.startswith("#") and len(color) == 7:
        hex_color = color[1:]
        alpha = int(max(0.0, min(1.0, opacity)) * 255)
        return f"#{alpha:02x}{hex_color}"
    # named CSS colors or malformed — return as-is
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



