# routes/home.py
from flask import Blueprint, render_template, session
from models.user import User

home_bp = Blueprint("home", __name__)

def current_user():
    uid = session.get("user_id")
    return User.query.get(uid) if uid else None

@home_bp.context_processor
def inject_user():
    return {"current_user": current_user()}

@home_bp.route("/")
def index():
    return render_template("index.html")
