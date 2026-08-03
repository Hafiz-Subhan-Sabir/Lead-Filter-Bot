"""
Paste this into PythonAnywhere:
  /var/www/rsdev_pythonanywhere_com_wsgi.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path("/home/rsdev/lead-filter-bot")
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

# Flask WSGI app (reliable on PythonAnywhere free)
from pa_app import application  # noqa: E402, F401
