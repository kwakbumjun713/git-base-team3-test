# config.py
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or os.urandom(32)

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "secure.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False

    RESEARCH_UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    RESEARCH_ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

    CTFTIME_API_URL = "https://ctftime.org/api/v1/events/"
    CTFTIME_CACHE_SECONDS = 900
    CTFTIME_LOOKAHEAD_SECONDS = 60 * 60 * 24 * 90  # 90 days
    CTFTIME_TIMEOUT = 10
    CTFTIME_USER_AGENT = "HSpaceCatalog/1.0"
