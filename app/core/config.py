"""Configuration settings and environment variables loader."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Project base paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"

# Load environment variables from .env if present
if ENV_FILE.is_file():
    load_dotenv(dotenv_path=ENV_FILE)
else:
    load_dotenv()

# Assets and storage paths
ASSETS_DIR = BASE_DIR / "assets"
AUDIO_DIR = ASSETS_DIR / "audio"
VIDEO_DIR = ASSETS_DIR / "video"
OUTPUT_DIR = ASSETS_DIR / "output"
DATA_DIR = BASE_DIR / "data"

# Ensure runtime directories exist
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Database
DB_PATH = DATA_DIR / "stoic_videos.db"

# Gemini AI Settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview").strip()

# TTS Settings
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "es-ES-AlvaroNeural").strip()
