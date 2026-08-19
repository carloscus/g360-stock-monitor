from pathlib import Path
import os

try:
    import tomllib
except ImportError:
    import tomli as tomllib

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ASSETS_DIR = BASE_DIR / "assets"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LINEAS_FILE = DATA_DIR / "lineas.json"
SNAPSHOT_DIR = BASE_DIR / ".snapshots"

S1_API_URL = "https://g360-stock-api.onrender.com/api/v1"
S1_API_KEY = os.environ.get("S1_API_KEY", "cipsa2026")

VERSION_CHECK_URL = S1_API_URL + "/version"
VERSION_CACHE_FILE = DATA_DIR / ".version_check.json"
VERSION_CHECK_INTERVAL = 86400

AUTO_REFRESH_INTERVAL = 900

TEMP_DIR_PREFIX = "g360_stock_monitor_"

WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
WINDOW_MIN_WIDTH = 900
WINDOW_MIN_HEIGHT = 600

CACHE_FILE = DATA_DIR / ".last_raw.json"

PRIMARY_CATEGORIES = {"VINIBALL", "VINIFAN", "REPRESENTADAS"}

# Patrón para detectar almacenes "informativos" por código (s*, 118, 122).
import re
SPECIAL_WAREHOUSE_RE = re.compile(r"^(?:s\d+|118|122)$", re.IGNORECASE)


def get_local_version() -> str:
    pyproject = BASE_DIR / "pyproject.toml"
    if not pyproject.exists():
        return "0.0.0"
    try:
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        return str(data.get("project", {}).get("version", "0.0.0"))
    except Exception:
        return "0.0.0"
