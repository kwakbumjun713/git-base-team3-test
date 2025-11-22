# routes/auth.py
from flask import Blueprint, render_template, redirect, url_for, session, flash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo, Regexp

from models.user import User
from extensions import db, limiter

auth_bp = Blueprint("auth", __name__)

# --------------------------- #
#        WTForms 정의
# --------------------------- #

class RegisterForm(FlaskForm):
    username = StringField(
        "아이디",
        validators=[
            DataRequired(),
            Length(min=4, max=20),
            Regexp(r"^[a-zA-Z0-9_]+$", message="아이디는 영문/숫자/밑줄만 가능합니다."),
        ],
    )
    password = PasswordField(
        "비밀번호",
        validators=[
            DataRequired(),
            Length(min=10, message="비밀번호는 최소 10자 이상이어야 합니다."),
            Regexp(r".*[A-Z].*", message="비밀번호에는 대문자 1개 이상 포함"),
            Regexp(r".*[a-z].*", message="비밀번호에는 소문자 1개 이상 포함"),
            Regexp(r".*[0-9].*", message="비밀번호에는 숫자 1개 이상 포함"),
            Regexp(
                r".*[\!\@\#\$\%\^\&\*\(\)\_\+\-\=\[\]\{\}\|\;\:\'\",\.\/\<\>\?].*",
                message="비밀번호에는 특수문자 1개 이상 포함",
            ),
        ],
    )
    password_confirm = PasswordField(
        "비밀번호 확인",
        validators=[
            DataRequired(),
            EqualTo("password", message="비밀번호가 일치하지 않습니다."),
        ],
    )
    submit = SubmitField("회원가입")


class LoginForm(FlaskForm):
    username = StringField("아이디", validators=[DataRequired()])
    password = PasswordField("비밀번호", validators=[DataRequired()])
    submit = SubmitField("로그인")


# --------------------------- #
#        로그인
# --------------------------- #

@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    form = LoginForm()

    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data

        user = User.query.filter_by(username=username).first()

        # 로그인 실패 → flash 없음 (보안상 good)
        if not user or not user.check_password(password):
            return render_template("login.html", form=form)

        session.clear()
        session["user_id"] = user.id

        return redirect(url_for("home.index"))

    return render_template("login.html", form=form)


# --------------------------- #
#        회원가입
# --------------------------- #

@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("3 per minute")
def register():
    form = RegisterForm()

    if form.validate_on_submit():
        username = form.username.data.strip()

        # 아이디 중복 시 flash 출력 안 함 (정보 노출 방지)
        if User.query.filter_by(username=username).first():
            return render_template("register.html", form=form)

        user = User(username=username)
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        # 🔥 회원가입 성공 flash — 단 하나만 표시됨
        flash("회원가입이 완료되었습니다!", "success")

        return redirect(url_for("auth.login"))

    return render_template("register.html", form=form)


# --------------------------- #
#        로그아웃
# --------------------------- #

@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("home.index"))
