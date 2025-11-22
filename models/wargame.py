from datetime import datetime

from extensions import db


class WargameChallenge(db.Model):
    __tablename__ = "wargame_challenges"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(32), nullable=False, default="중급")
    category = db.Column(db.String(64), nullable=False, default="Misc")
    flag_answer = db.Column(db.String(255), nullable=False)
    hint = db.Column(db.String(255))
    reward_points = db.Column(db.Integer, default=0)
    attachment_path = db.Column(db.String(255))
    is_community = db.Column(db.Boolean, default=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    author_name = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    attempts = db.relationship(
        "WargameAttempt",
        back_populates="challenge",
        cascade="all, delete-orphan",
    )


class WargameAttempt(db.Model):
    __tablename__ = "wargame_attempts"

    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(
        db.Integer,
        db.ForeignKey("wargame_challenges.id"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    submitted_flag = db.Column(db.String(255))
    is_correct = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    challenge = db.relationship("WargameChallenge", back_populates="attempts")
    user = db.relationship("User")
