# models/minigame.py
from datetime import datetime
from extensions import db


class TetrisScore(db.Model):
    __tablename__ = "tetris_scores"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    level = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 관계 설정
    user = db.relationship('User', backref=db.backref('tetris_scores', lazy=True))

    def __repr__(self):
        return f'<TetrisScore {self.user_id}: {self.score}>'
