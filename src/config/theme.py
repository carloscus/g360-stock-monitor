import json
from pathlib import Path

ACCENT = "#10B981"
ACCENT_DARK = "#047857"

DARK_COLORS = {
    "accent": ACCENT,
    "accent_dark": ACCENT_DARK,
    "success": "#34D399",
    "warning": "#F59E0B",
    "error": "#EF4444",
    "info": "#3B82F6",
    "violet": "#8B5CF6",
    "pink": "#EC4899",
    "cyan": "#06B6D4",
    "orange": "#F97316",
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



