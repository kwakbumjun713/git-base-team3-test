from datetime import datetime

from extensions import db


class Competition(db.Model):
    __tablename__ = "competitions"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    organizer = db.Column(db.String(255))
    apply_start = db.Column(db.String(32))
    apply_end = db.Column(db.String(32))
    event_start = db.Column(db.String(32))
    event_end = db.Column(db.String(32))
    summary = db.Column(db.Text)
    mode = db.Column(db.String(100))
    tags = db.Column(db.Text)
    difficulty = db.Column(db.String(50))
    cover_image = db.Column(db.String(512))
    approved = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    posts = db.relationship(
        "TeamPost",
        back_populates="competition",
        cascade="all, delete",
    )


class TeamPost(db.Model):
    __tablename__ = "team_posts"

    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey("competitions.id"))
    custom_competition = db.Column(db.String(255))
    event_start = db.Column(db.String(32))
    event_end = db.Column(db.String(32))
    title = db.Column(db.String(255), nullable=False)
    owner = db.Column(db.String(255))
    summary = db.Column(db.Text)
    requirements = db.Column(db.Text)
    tags = db.Column(db.Text)
    team_size = db.Column(db.String(80))
    level = db.Column(db.String(50))
    use_random_matching = db.Column(db.Boolean, default=True)
    phase = db.Column(db.String(32), default="모집 중")
    cover_image = db.Column(db.String(512))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    competition = db.relationship("Competition", back_populates="posts")
    applications = db.relationship(
        "TeamApplication",
        back_populates="post",
        cascade="all, delete-orphan",
    )


class TeamApplication(db.Model):
    __tablename__ = "team_applications"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(
        db.Integer,
        db.ForeignKey("team_posts.id"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    applicant_name = db.Column(db.String(255), nullable=False)
    contact = db.Column(db.String(255))
    message = db.Column(db.Text)
    desired_role = db.Column(db.String(255))
    level = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    post = db.relationship("TeamPost", back_populates="applications")
