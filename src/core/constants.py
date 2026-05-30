from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ASSETS_DIR = BASE_DIR / "assets"
DATA_DIR = ASSETS_DIR / "data"
LINEAS_FILE = DATA_DIR / "lineas.json"
SNAPSHOT_DIR = BASE_DIR / ".snapshots"

S1_URL = (
    "http://appweb.cipsa.com.pe:8054/AlmacenStock/DownLoadFiles"
    "?value=%7B%22parametroX1%22%3A%220%22%2C%22parametroX2%22%3A%220%22%7D"
)
# Equivalente legible: http://appweb.cipsa.com.pe:8054/AlmacenStock/DownLoadFiles?value={"parametroX1":"0","parametroX2":"0"}

TEMP_DIR_PREFIX = "g360_stock_monitor_"

WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
WINDOW_MIN_WIDTH = 900
WINDOW_MIN_HEIGHT = 600
