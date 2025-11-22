import random
from datetime import datetime, date

from flask import Blueprint, flash, get_flashed_messages, jsonify, redirect, render_template, request, url_for, g
from sqlalchemy import func, inspect, text, or_
from sqlalchemy.exc import NoSuchTableError
from sqlalchemy.orm import joinedload
from extensions import csrf, db, limiter
from models.research import Competition, TeamApplication, TeamPost
from services.ctftime import fetch_ctftime_events, get_ctftime_event

PHASE_TABS = ["전체", "모집 중", "진행중", "완료"]
LEVELS = ["초급", "중급", "고급"]

research_bp = Blueprint("research", __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _coerce_date(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str) and value:
        normalized = value.strip()
        if normalized:
            try:
                normalized = normalized.replace("Z", "+00:00")
                return datetime.fromisoformat(normalized)
            except ValueError:
                pass
        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(normalized, fmt)
            except ValueError:
                continue
    return None


def _to_datetime_local(value):
    dt = _coerce_date(value)
    if not dt:
        return ""
    return dt.strftime("%Y-%m-%dT%H:%M")


def _normalize_datetime_str(value):
    if not value:
        return None
    dt = _coerce_date(value)
    if not dt:
        return value
    return dt.replace(microsecond=0).isoformat()


def format_period(start, end):
    def _fmt(value):
        as_date = _coerce_date(value)
        return as_date.strftime("%m/%d %H:%M") if as_date else ""

    s = _fmt(start)
    e = _fmt(end)
    if s and e:
        return f"{s} - {e}"
    return s or e or "상시"


def d_day_badge(target):
    as_date = _coerce_date(target)
    if not as_date:
        return ""
    delta = (as_date.date() - datetime.utcnow().date()).days
    if delta > 0:
        return f"{delta}일 후 마감"
    if delta == 0:
        return "오늘 마감"
    return f"{abs(delta)}일 경과"


def parse_tags(raw):
    if not raw:
        return []
    return [tag.strip() for tag in raw.split(",") if tag.strip()]


def fetch_competitions(approved_only=True):
    query = Competition.query
    if approved_only:
        query = query.filter(Competition.approved.is_(True))
    competitions = []
    for comp in query.order_by(Competition.created_at.desc()).all():
        data = {
            "id": comp.id,
            "title": comp.title,
            "organizer": comp.organizer,
            "summary": comp.summary,
            "mode": comp.mode,
            "difficulty": comp.difficulty,
            "cover_image": comp.cover_image,
            "tags": parse_tags(comp.tags),
            "apply_period": format_period(comp.apply_start, comp.apply_end),
            "event_period": format_period(comp.event_start, comp.event_end),
            "apply_badge": d_day_badge(comp.apply_end),
            "event_badge": d_day_badge(comp.event_start or comp.event_end),
            "approved": comp.approved,
        }
        competitions.append(data)
    return competitions


def _ensure_competition_from_event(event):
    title = event.get("title")
    if not title:
        return None
    competition = Competition.query.filter_by(title=title).first()
    start_str = _normalize_datetime_str(event.get("start"))
    finish_str = _normalize_datetime_str(event.get("finish"))
    summary = event.get("description_short") or event.get("description")
    mode = event.get("format")
    location = event.get("location")
    cover_image = event.get("logo")

    if competition:
        updated = False
        if start_str and competition.event_start != start_str:
            competition.event_start = start_str
            competition.apply_start = start_str
            updated = True
        if finish_str and competition.event_end != finish_str:
            competition.event_end = finish_str
            competition.apply_end = finish_str
            updated = True
        if summary and competition.summary != summary:
            competition.summary = summary
            updated = True
        if mode and competition.mode != mode:
            competition.mode = mode
            updated = True
        if location and competition.tags != location:
            competition.tags = location
            updated = True
        if cover_image and competition.cover_image != cover_image:
            competition.cover_image = cover_image
            updated = True
        if updated:
            db.session.commit()
        return competition

    competition = Competition(
        title=title,
        organizer=None,
        apply_start=start_str,
        apply_end=start_str,
        event_start=start_str,
        event_end=finish_str,
        summary=summary,
        mode=mode,
        tags=location,
        difficulty=None,
        cover_image=cover_image,
        approved=True,
    )
    db.session.add(competition)
    db.session.commit()
    return competition


def _serialize_post(post, current_user_id=None):
    competition = post.competition
    tags = parse_tags(post.tags)
    competition_tags = parse_tags(competition.tags) if competition else []
    apply_start = competition.apply_start if competition else None
    apply_end = competition.apply_end if competition else None
    event_start = post.event_start or (competition.event_start if competition else None)
    event_end = post.event_end or (competition.event_end if competition else None)
    apply_period = format_period(apply_start, apply_end)
    event_period = format_period(event_start, event_end)

    competition_title = competition.title if competition else post.custom_competition
    return {
        "id": post.id,
        "title": post.title,
        "owner": post.owner,
        "summary": post.summary,
        "requirements": post.requirements,
        "tags": tags,
        "team_size": post.team_size,
        "level": post.level,
        "use_random_matching": post.use_random_matching,
        "phase": post.phase,
        "created_at": post.created_at,
        "applicant_count": len(post.applications or []),
        "competition_title": competition_title,
        "competition_organizer": competition.organizer if competition else None,
        "competition_summary": competition.summary if competition else None,
        "competition_mode": competition.mode if competition else None,
        "competition_tags": competition_tags,
        "competition_difficulty": competition.difficulty if competition else None,
        "apply_period": apply_period,
        "event_period": event_period,
        "apply_badge": d_day_badge(apply_end),
        "event_badge": d_day_badge(event_start),
        "has_applied": bool(
            current_user_id
            and any(app.user_id == current_user_id for app in (post.applications or []))
        ),
    }


def fetch_team_posts(phase=None, limit=None, current_user_id=None):
    query = (
        TeamPost.query.options(
            joinedload(TeamPost.competition),
            joinedload(TeamPost.applications),
        )
        .order_by(TeamPost.created_at.desc())
    )
    if phase and phase != "전체":
        query = query.filter(TeamPost.phase == phase)
    if limit:
        query = query.limit(int(limit))
    return [_serialize_post(post, current_user_id) for post in query.all()]


def phase_counts():
    rows = (
        db.session.query(TeamPost.phase, func.count(TeamPost.id))
        .group_by(TeamPost.phase)
        .all()
    )
    counts = {phase: total for phase, total in rows}
    counts["전체"] = sum(counts.values())
    for tab in PHASE_TABS:
        counts.setdefault(tab, 0)
    return counts


def _sanitize_phase(value):
    return value if value in PHASE_TABS else "전체"


@research_bp.before_app_request
def _ensure_team_post_columns():
    engine = db.engine
    inspector = inspect(engine)
    try:
        columns = [col["name"] for col in inspector.get_columns("team_posts")]
    except NoSuchTableError:
        return
    required = {
        "custom_competition": "VARCHAR(255)",
        "event_start": "VARCHAR(32)",
        "event_end": "VARCHAR(32)",
    }
    missing = [name for name in required if name not in columns]
    if missing:
        with engine.connect() as conn:
            for name in missing:
                conn.execute(
                    text(f"ALTER TABLE team_posts ADD COLUMN {name} {required[name]}")
                )
            conn.commit()

    try:
        application_columns = [
            col["name"] for col in inspector.get_columns("team_applications")
        ]
    except NoSuchTableError:
        return
    if "user_id" not in application_columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE team_applications ADD COLUMN user_id INTEGER"))
            conn.commit()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@research_bp.route("/research", methods=["GET", "POST"])
@csrf.exempt
def research():
    if not g.user:
        return redirect(url_for("auth.login"))
    selected_phase = _sanitize_phase(request.args.get("phase", "전체"))
    competitions = fetch_competitions()
    prefill = {
        "competition": request.args.get("prefill_competition", ""),
        "title": request.args.get("prefill_title", ""),
        "summary": request.args.get("prefill_summary", ""),
        "requirements": request.args.get("prefill_requirements", ""),
        "team_size": request.args.get("prefill_team_size", ""),
        "level": request.args.get("prefill_level", ""),
        "event_start": request.args.get("prefill_event_start", ""),
        "event_end": request.args.get("prefill_event_end", ""),
    }

    if request.method == "POST":
        form_type = request.form.get("form_type")
        if form_type == "team_post":
            return _handle_team_post_submission()
        if form_type == "team_application":
            return _handle_team_application_submission(selected_phase)

    user_id = g.user.id if g.user else None
    posts = fetch_team_posts(selected_phase, current_user_id=user_id)
    counts = phase_counts()
    return render_template(
        "research.html",
        posts=posts,
        phase_counts=counts,
        phases=PHASE_TABS,
        active_phase=selected_phase,
        competitions=competitions,
        levels=LEVELS,
        messages=get_flashed_messages(),
        prefill=prefill,
    )


@research_bp.route("/catalog")
def catalog():
    if not g.user:
        return redirect(url_for("auth.login"))
    events = fetch_ctftime_events(limit=30)
    return render_template("catalog.html", events=events, levels=LEVELS)


@research_bp.route("/catalog/<int:event_id>/team")
def catalog_team(event_id):
    if not g.user:
        return redirect(url_for("auth.login"))
    event = get_ctftime_event(event_id)
    if not event:
        flash("대회 정보를 불러올 수 없습니다.", "error")
        return redirect(url_for("research.catalog"))

    event_title = event.get("title") or ""
    _ensure_competition_from_event(event)
    start_local = _to_datetime_local(event.get("start"))
    finish_local = _to_datetime_local(event.get("finish"))
    requirements = []
    if event.get("format"):
        requirements.append(f"대회 형식: {event['format']}")
    if event.get("onsite") is not None:
        requirements.append("현장 진행" if event["onsite"] else "온라인 진행")
    if event.get("start_display") and event.get("finish_display"):
        requirements.append(f"기간: {event['start_display']} ~ {event['finish_display']}")
    if event.get("location"):
        requirements.append(f"지역: {event['location']}")

    params = {
        "prefill_competition": event_title,
        "prefill_title": f"{event_title} 팀 모집" if event_title else "",
        "prefill_summary": event.get("description_short", "") or "",
        "prefill_requirements": " / ".join(requirements),
        "prefill_event_start": start_local,
        "prefill_event_end": finish_local,
    }
    return redirect(url_for("research.research", **params))


@research_bp.route("/team/<int:post_id>")
def team_detail(post_id):
    if not g.user:
        return redirect(url_for("auth.login"))
    post = (
        TeamPost.query.options(
            joinedload(TeamPost.competition),
            joinedload(TeamPost.applications),
        ).get_or_404(post_id)
    )
    serialized = _serialize_post(post, g.user.id)
    applications = (
        TeamApplication.query.filter_by(post_id=post.id)
        .order_by(TeamApplication.created_at.desc())
        .all()
    )
    my_application = next(
        (app for app in applications if app.user_id == g.user.id), None
    )
    return render_template(
        "team_detail.html",
        post=serialized,
        raw_post=post,
        applications=applications,
        my_application=my_application,
        levels=LEVELS,
    )


def _handle_team_post_submission():
    title = (request.form.get("title") or "").strip()
    if not title:
        flash("팀명/프로젝트명을 입력해 주세요.", "error")
        return redirect(url_for("research.research"))

    phase = _sanitize_phase(request.form.get("phase", "모집 중"))
    competition_input = (request.form.get("competition_input") or "").strip()
    competition_id = None
    custom_competition = None
    if competition_input:
        existing = Competition.query.filter_by(title=competition_input).first()
        if existing:
            competition_id = existing.id
        else:
            custom_competition = competition_input

    event_start = _normalize_datetime_str(request.form.get("event_start"))
    event_end = _normalize_datetime_str(request.form.get("event_end"))

    post = TeamPost(
        competition_id=competition_id,
        custom_competition=custom_competition,
        event_start=event_start,
        event_end=event_end,
        title=title,
        owner=(request.form.get("owner") or "").strip(),
        summary=request.form.get("summary"),
        requirements=request.form.get("requirements"),
        tags=request.form.get("tags"),
        team_size=request.form.get("team_size"),
        level=request.form.get("level"),
        use_random_matching=request.form.get("use_random_matching") == "on",
        phase=phase,
    )
    db.session.add(post)
    db.session.commit()
    flash("팀 모집 글이 등록되었습니다.")
    return redirect(url_for("research.research"))


def _handle_team_application_submission(selected_phase):
    post_id = request.form.get("post_id")
    try:
        post_id_int = int(post_id)
    except (TypeError, ValueError):
        flash("지원 대상 팀을 찾을 수 없습니다.", "error")
        return redirect(url_for("research.research", phase=selected_phase))

    post = TeamPost.query.get(post_id_int)
    if not post:
        flash("해당 팀을 찾을 수 없습니다.", "error")
        return redirect(url_for("research.research", phase=selected_phase))

    next_url = request.form.get("next")
    if next_url and not next_url.startswith("/"):
        next_url = None

    existing = None
    if g.user:
        existing = TeamApplication.query.filter_by(
            post_id=post.id, user_id=g.user.id
        ).first()
    if existing:
        flash("이미 지원한 팀입니다.", "info")
        if next_url:
            return redirect(next_url)
        return redirect(url_for("research.research", phase=selected_phase))

    application = TeamApplication(
        post_id=post.id,
        user_id=g.user.id if g.user else None,
        applicant_name=(request.form.get("applicant_name") or "").strip(),
        contact=request.form.get("contact"),
        message=request.form.get("message"),
        desired_role=request.form.get("desired_role"),
        level=request.form.get("level"),
    )
    db.session.add(application)
    db.session.commit()
    flash("지원이 접수되었습니다. 팀 리더에게 전달됩니다.")
    if next_url:
        return redirect(next_url)
    return redirect(url_for("research.research", phase=selected_phase))


@research_bp.route("/api/random-match", methods=["POST"])
@csrf.exempt
@limiter.limit("20 per minute")
def api_random_match():
    payload = request.get_json(silent=True) or request.form or {}
    competition_id = payload.get("competition_id") or None
    competition_title = payload.get("competition_title") or None
    level = payload.get("level") or None

    query = TeamPost.query.options(joinedload(TeamPost.competition))
    if competition_id:
        try:
            competition_id = int(competition_id)
            query = query.filter(TeamPost.competition_id == competition_id)
        except (TypeError, ValueError):
            competition_id = None
    if competition_title:
        query = query.filter(
            or_(
                TeamPost.custom_competition == competition_title,
                TeamPost.competition.has(Competition.title == competition_title),
            )
        )
    if level:
        query = query.filter(TeamPost.level == level)

    posts = query.all()
    if not posts:
        posts = TeamPost.query.options(joinedload(TeamPost.competition)).all()

    sample_size = min(3, len(posts))
    matches = random.sample(posts, sample_size) if posts else []

    data = [
        {
            "id": post.id,
            "title": post.title,
            "owner": post.owner,
            "summary": post.summary,
            "team_size": post.team_size,
            "level": post.level,
            "phase": post.phase,
            "competition_title": post.competition.title
            if post.competition
            else post.custom_competition,
        }
        for post in matches
    ]
    return jsonify({"matches": data})
