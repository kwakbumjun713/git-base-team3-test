# config.py
import os

from dotenv import load_dotenv
from urllib.parse import quote_plus

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or os.urandom(32)

    DB_USER = os.environ.get("DB_USER", "huser")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "hs1234!!")
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = os.environ.get("DB_PORT", "3306")
    DB_NAME = os.environ.get("DB_NAME", "hspace")

    _ENCODED_USER = quote_plus(DB_USER)
    _ENCODED_PASSWORD = quote_plus(DB_PASSWORD)
    _DEFAULT_MYSQL = (
        f"mysql+pymysql://{_ENCODED_USER}:{_ENCODED_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )
    _DEFAULT_SQLITE = f"sqlite:///{os.path.join(BASE_DIR, 'secure.db')}"

    _engine = os.environ.get("DB_ENGINE", "sqlite").lower()
    _fallback_uri = _DEFAULT_MYSQL if _engine == "mysql" else _DEFAULT_SQLITE
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", _fallback_uri)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False

    RESEARCH_UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    RESEARCH_ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

    WARGAME_UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "wargame_attachments")
    WARGAME_ALLOWED_EXTENSIONS = {
        "zip",
        "tar",
        "gz",
        "tgz",
        "bz2",
        "7z",
        "txt",
        "pdf",
        "md",
    }
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 8 * 1024 * 1024))

    CTFTIME_API_URL = "https://ctftime.org/api/v1/events/"
    CTFTIME_CACHE_SECONDS = 900
    CTFTIME_LOOKAHEAD_SECONDS = 60 * 60 * 24 * 90  # 90 days
    CTFTIME_TIMEOUT = 10
    CTFTIME_USER_AGENT = "HSpaceCatalog/1.0"
