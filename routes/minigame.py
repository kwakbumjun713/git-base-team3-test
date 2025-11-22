# routes/minigame.py
from flask import Blueprint, render_template, request, jsonify, session, g
from extensions import db
from models.user import User
from models.minigame import TetrisScore

minigame_bp = Blueprint("minigame", __name__, url_prefix="/mini_game")


def current_user():
    uid = session.get("user_id")
    return User.query.get(uid) if uid else None


@minigame_bp.context_processor
def inject_user():
    return {"current_user": current_user()}


@minigame_bp.route("/")
def index():
    """테트리스 게임 페이지"""
    # 상위 10개의 점수를 가져와서 순위표에 표시
    leaderboard = TetrisScore.query.order_by(
        TetrisScore.score.desc()
    ).limit(10).all()

    return render_template("minigame.html", leaderboard=leaderboard)


@minigame_bp.route("/submit_score", methods=["POST"])
def submit_score():
    """게임 종료 시 점수를 저장하는 API"""
    if not g.user:
        return jsonify({"success": False, "error": "로그인이 필요합니다."}), 401

    try:
        data = request.get_json()
        score = data.get("score", 0)
        level = data.get("level", 1)

        # 점수 저장
        new_score = TetrisScore(
            user_id=g.user.id,
            score=score,
            level=level
        )
        db.session.add(new_score)
        db.session.commit()

        return jsonify({"success": True, "message": "점수가 저장되었습니다."})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@minigame_bp.route("/leaderboard")
def leaderboard():
    """리더보드 전체 데이터를 반환하는 API"""
    scores = TetrisScore.query.order_by(
        TetrisScore.score.desc()
    ).limit(50).all()

    leaderboard_data = [
        {
            "rank": idx + 1,
            "username": score.user.username,
            "score": score.score,
            "level": score.level,
            "created_at": score.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
        for idx, score in enumerate(scores)
    ]

    return jsonify({"success": True, "leaderboard": leaderboard_data})
