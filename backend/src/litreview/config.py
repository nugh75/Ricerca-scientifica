from pathlib import Path

APP_DIR = Path.home() / ".litreview"
DB_PATH = APP_DIR / "library.db"
PDF_DIR = APP_DIR / "pdfs"
KEYRING_SERVICE = "litreview"

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
