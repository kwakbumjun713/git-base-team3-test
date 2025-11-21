import os
from uuid import uuid4

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, url_for
from sqlalchemy import func, or_, inspect, text
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from extensions import db
from models.user import User
from models.wargame import WargameAttempt, WargameChallenge

wargame_bp = Blueprint("wargame", __name__, url_prefix="/wargame")


def _ensure_seed_challenges():
    seeds = [
        {
            "title": "Satellite Beacon",
            "summary": "우주 정거장에서 발신되는 비콘 신호를 분석해 플래그를 확보하세요. 간단한 암호 해독 문제입니다.",
            "difficulty": "초급",
            "category": "Crypto",
            "flag_answer": "FLAG{ORBITAL_SIGNAL}",
            "hint": "시저 + 주기 13",
            "reward_points": 50,
        },
        {
            "title": "Nebula Terminal",
            "summary": "폐쇄형 단말기에 남아있는 로그를 추적해 관리자 토큰을 복구하세요.",
            "difficulty": "중급",
            "category": "Pwnable",
            "flag_answer": "FLAG{STACK_WALKER}",
            "hint": "스택 오버플로우",
            "reward_points": 120,
        },
        {
            "title": "Black Hole Storage",
            "summary": "S3 호환 버킷이 잘못 설정되어 있습니다. 노출된 백업에서 플래그를 찾아보세요.",
            "difficulty": "고급",
            "category": "Cloud",
            "flag_answer": "FLAG{PUBLIC_BUCKET_MISCONFIG}",
            "hint": "리스트 권한 확인",
            "reward_points": 200,
        },
    ]
    existing_titles = {
        title for (title,) in db.session.query(WargameChallenge.title).all()
    }
    created = False
    for seed in seeds:
        if seed["title"] in existing_titles:
            continue
        challenge = WargameChallenge(**seed, is_community=False, author_name="시스템")
        db.session.add(challenge)
        created = True
    if created:
        db.session.commit()


def _ensure_attachment_column():
    try:
        inspector = inspect(db.engine)
        columns = {col["name"] for col in inspector.get_columns("wargame_challenges")}
    except Exception:
        return
    if "attachment_path" in columns:
        return
    column_type = "TEXT" if db.engine.url.get_backend_name().startswith("sqlite") else "VARCHAR(255)"
    with db.engine.begin() as connection:
        connection.execute(
            text(f"ALTER TABLE wargame_challenges ADD COLUMN attachment_path {column_type}")
        )


def _allowed_attachment(filename):
    if not filename or "." not in filename:
        return False
    allowed = current_app.config.get("WARGAME_ALLOWED_EXTENSIONS", set())
    return filename.rsplit(".", 1)[1].lower() in allowed


def _save_attachment(file_storage):
    filename = secure_filename(file_storage.filename or "")
    if not filename:
        return None
    upload_root = current_app.config["WARGAME_UPLOAD_FOLDER"]
    os.makedirs(upload_root, exist_ok=True)
    unique_name = f"{uuid4().hex}_{filename}"
    target_path = os.path.join(upload_root, unique_name)
    file_storage.save(target_path)
    static_root = current_app.static_folder
    rel_path = os.path.relpath(target_path, static_root).replace("\\", "/")
    if rel_path.startswith(".."):  # folder misconfiguration guard
        raise ValueError("Upload folder must live inside static directory")
    return rel_path


def _serialize_challenge(challenge):
    solved_count = sum(1 for attempt in (challenge.attempts or []) if attempt.is_correct)
    return {
        "id": challenge.id,
        "title": challenge.title,
        "summary": challenge.summary,
        "difficulty": challenge.difficulty,
        "category": challenge.category,
        "hint": challenge.hint,
        "reward_points": challenge.reward_points,
        "is_community": challenge.is_community,
        "author_name": challenge.author_name or "익명",
        "created_at": challenge.created_at,
        "solved_count": solved_count,
        "attachment_path": challenge.attachment_path,
    }


def _load_leaderboard(limit=5):
    rows = (
        db.session.query(User.username, func.count(WargameAttempt.id).label("solves"))
        .join(User, User.id == WargameAttempt.user_id)
        .filter(WargameAttempt.is_correct.is_(True))
        .group_by(User.id, User.username)
        .order_by(func.count(WargameAttempt.id).desc(), func.min(WargameAttempt.created_at))
        .limit(limit)
        .all()
    )
    return [{"username": username, "solved": solves} for username, solves in rows]


@wargame_bp.route("/", methods=["GET"])
def dashboard():
    _ensure_attachment_column()
    _ensure_seed_challenges()

    filters = {
        "difficulty": request.args.get("difficulty", "all"),
        "category": request.args.get("category", "all"),
        "search": (request.args.get("search") or "").strip(),
        "sort": request.args.get("sort", "newest"),
    }

    challenge_query = WargameChallenge.query.options(joinedload(WargameChallenge.attempts))
    if filters["difficulty"] != "all":
        challenge_query = challenge_query.filter(
            WargameChallenge.difficulty == filters["difficulty"]
        )
    if filters["category"] != "all":
        challenge_query = challenge_query.filter(WargameChallenge.category == filters["category"])
    if filters["search"]:
        like_expr = f"%{filters['search']}%"
        challenge_query = challenge_query.filter(
            or_(
                WargameChallenge.title.ilike(like_expr),
                WargameChallenge.summary.ilike(like_expr),
            )
        )

    if filters["sort"] == "reward":
        challenge_query = challenge_query.order_by(WargameChallenge.reward_points.desc())
    elif filters["sort"] == "oldest":
        challenge_query = challenge_query.order_by(WargameChallenge.created_at.asc())
    else:
        challenge_query = challenge_query.order_by(WargameChallenge.created_at.desc())

    challenges = challenge_query.all()
    serialized = [_serialize_challenge(ch) for ch in challenges]
    if filters["sort"] == "popular":
        serialized.sort(key=lambda item: item["solved_count"], reverse=True)

    featured = serialized[0] if serialized else None

    stats = {
        "total_challenges": db.session.query(func.count(WargameChallenge.id)).scalar() or 0,
        "community_count": db.session.query(func.count(WargameChallenge.id))
        .filter(WargameChallenge.is_community.is_(True))
        .scalar()
        or 0,
        "solved_total": db.session.query(func.count(WargameAttempt.id))
        .filter(WargameAttempt.is_correct.is_(True))
        .scalar()
        or 0,
    }

    recent_creations = (
        WargameChallenge.query.options(joinedload(WargameChallenge.attempts))
        .filter(WargameChallenge.is_community.is_(True))
        .order_by(WargameChallenge.created_at.desc())
        .limit(5)
        .all()
    )
    recent_creations = [_serialize_challenge(ch) for ch in recent_creations]

    categories = [
        category
        for (category,) in db.session.query(WargameChallenge.category)
        .distinct()
        .order_by(WargameChallenge.category.asc())
        .all()
        if category
    ]

    leaderboard = _load_leaderboard()

    user_stats = None
    recent_attempts = []
    if g.user:
        total_attempts = (
            db.session.query(func.count(WargameAttempt.id))
            .filter(WargameAttempt.user_id == g.user.id)
            .scalar()
            or 0
        )
        total_solves = (
            db.session.query(func.count(WargameAttempt.id))
            .filter(
                WargameAttempt.user_id == g.user.id,
                WargameAttempt.is_correct.is_(True),
            )
            .scalar()
            or 0
        )
        solved_points = (
            db.session.query(func.coalesce(func.sum(WargameChallenge.reward_points), 0))
            .select_from(WargameAttempt)
            .join(WargameChallenge, WargameChallenge.id == WargameAttempt.challenge_id)
            .filter(
                WargameAttempt.user_id == g.user.id,
                WargameAttempt.is_correct.is_(True),
            )
            .scalar()
            or 0
        )
        favorite_category = (
            db.session.query(
                WargameChallenge.category, func.count(WargameChallenge.id).label("cnt")
            )
            .select_from(WargameAttempt)
            .join(WargameChallenge, WargameAttempt.challenge_id == WargameChallenge.id)
            .filter(
                WargameAttempt.user_id == g.user.id,
                WargameAttempt.is_correct.is_(True),
            )
            .group_by(WargameChallenge.category)
            .order_by(func.count(WargameChallenge.id).desc())
            .first()
        )
        user_stats = {
            "total_attempts": total_attempts,
            "total_solves": total_solves,
            "accuracy": round((total_solves / total_attempts) * 100, 1) if total_attempts else 0,
            "favorite_category": favorite_category[0] if favorite_category else None,
            "reward_points": solved_points,
        }
        recent_attempt_rows = (
            WargameAttempt.query.filter_by(user_id=g.user.id)
            .options(joinedload(WargameAttempt.challenge))
            .order_by(WargameAttempt.created_at.desc())
            .limit(5)
            .all()
        )
        recent_attempts = [
            {
                "challenge": attempt.challenge.title if attempt.challenge else "알 수 없음",
                "difficulty": attempt.challenge.difficulty if attempt.challenge else "",
                "is_correct": attempt.is_correct,
                "submitted_flag": attempt.submitted_flag,
                "created_at": attempt.created_at,
            }
            for attempt in recent_attempt_rows
        ]

    return render_template(
        "wargame.html",
        featured=featured,
        challenges=serialized,
        stats=stats,
        recent_creations=recent_creations,
        leaderboard=leaderboard,
        filters=filters,
        categories=categories,
        user_stats=user_stats,
        recent_attempts=recent_attempts,
    )


def _require_login():
    if g.user:
        return None
    flash("로그인 후 이용해주세요.", "error")
    return redirect(url_for("auth.login", next=url_for("wargame.dashboard")))


@wargame_bp.route("/attempt", methods=["POST"])
def attempt_challenge():
    maybe_redirect = _require_login()
    if maybe_redirect:
        return maybe_redirect

    challenge_id = request.form.get("challenge_id")
    flag_text = (request.form.get("flag") or "").strip()
    challenge = WargameChallenge.query.get(challenge_id)
    if not challenge:
        flash("해당 문제를 찾을 수 없습니다.", "error")
        return redirect(url_for("wargame.dashboard"))

    is_correct = flag_text == challenge.flag_answer
    attempt = WargameAttempt(
        challenge_id=challenge.id,
        user_id=g.user.id,
        submitted_flag=flag_text,
        is_correct=is_correct,
    )
    db.session.add(attempt)
    db.session.commit()

    if is_correct:
        flash(f"🎉 {challenge.title} 문제를 해결했습니다!", "success")
    else:
        flash("아쉽지만 오답입니다. 힌트를 다시 확인해보세요.", "warning")
    return redirect(url_for("wargame.dashboard"))


@wargame_bp.route("/publish", methods=["POST"])
def publish_challenge():
    maybe_redirect = _require_login()
    if maybe_redirect:
        return maybe_redirect

    _ensure_attachment_column()
    title = (request.form.get("title") or "").strip()
    summary = (request.form.get("summary") or "").strip()
    difficulty = (request.form.get("difficulty") or "중급").strip()
    category = (request.form.get("category") or "Misc").strip()
    flag_answer = (request.form.get("flag") or "").strip()
    hint = (request.form.get("hint") or "").strip()
    upload_file = request.files.get("attachment")
    attachment_path = None

    if not title or not summary or not flag_answer:
        flash("제목, 설명, FLAG 값은 필수입니다.", "error")
        return redirect(url_for("wargame.dashboard"))

    allowed_difficulty = {"초급", "중급", "고급"}
    if difficulty not in allowed_difficulty:
        difficulty = "중급"

    if upload_file and upload_file.filename:
        if not _allowed_attachment(upload_file.filename):
            flash("허용되지 않은 첨부파일 형식입니다. 압축 또는 문서 파일만 등록해주세요.", "error")
            return redirect(url_for("wargame.dashboard"))
        try:
            attachment_path = _save_attachment(upload_file)
        except ValueError:
            flash("파일 저장 중 문제가 발생했습니다. 잠시 후 다시 시도해주세요.", "error")
            return redirect(url_for("wargame.dashboard"))

    challenge = WargameChallenge(
        title=title,
        summary=summary,
        difficulty=difficulty,
        category=category or "Misc",
        flag_answer=flag_answer,
        hint=hint or None,
        reward_points=80,
        attachment_path=attachment_path,
        is_community=True,
        author_id=g.user.id,
        author_name=g.user.username,
    )
    db.session.add(challenge)
    db.session.commit()
    flash("커뮤니티 문제를 업로드했습니다. 빠르게 검토 후 전파됩니다.", "success")
    return redirect(url_for("wargame.dashboard"))
