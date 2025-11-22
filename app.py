# app.py
from flask import Flask, g, session
from werkzeug.middleware.proxy_fix import ProxyFix
import config

# extensions.py에서 불러오기
from extensions import db, csrf, limiter


def create_app():
    app = Flask(__name__)
    app.config.from_object(config.Config)

    # 프록시 설정
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1)

    # 확장 초기화
    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # 모델 import (순환참조 방지)
    from models.user import User
    from models.research import Competition, TeamApplication, TeamPost
    from models.wargame import WargameAttempt, WargameChallenge
    from models.minigame import TetrisScore

    # 로그인 사용자 로딩
    @app.before_request
    def load_logged_in_user():
        user_id = session.get("user_id")
        g.user = User.query.get(user_id) if user_id else None

    # 보안 헤더
    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["X-XSS-Protection"] = "1; mode=block"
        resp.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; "
            "img-src 'self'; "
            "object-src 'none'; "
        )
        return resp

    # 블루프린트 등록
    from routes.home import home_bp
    from routes.auth import auth_bp
    from routes.research import research_bp
    from routes.wargame import wargame_bp
    from routes.minigame import minigame_bp

    app.register_blueprint(home_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(research_bp)
    app.register_blueprint(wargame_bp)
    app.register_blueprint(minigame_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=False)
