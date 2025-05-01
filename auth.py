# auth.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_
from models import db, User
from changes_queue import changes_queue
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__)

# configurable lockout parameters
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_TIME_MINUTES = 15

def _is_locked_out():
    """Returns True if the session is currently locked out."""
    lockout_until = session.get('lockout_until')
    if lockout_until:
        # compare stored ISO timestamp to now
        if datetime.fromisoformat(lockout_until) > datetime.utcnow():
            return True
        # lockout expired
        session.pop('lockout_until', None)
        session.pop('login_attempts', None)
    return False

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        # basic non-empty validation
        if not username or not email or not password:
            flash('Please fill in all fields!', 'error')
            return redirect(url_for('auth.register'))

        # using SQLAlchemy ORM with parameter binding to avoid SQL injection
        existing = User.query.filter(
            or_(User.username == username, User.email == email)
        ).first()
        if existing:
            flash('Username or Email already exists!', 'error')
            return redirect(url_for('auth.register'))

        # create and hash password
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        # enqueue sync event (without exposing raw password)
        changes_queue.put({
            "type":      "user_create",
            "user_id":   new_user.id,
            "username":  new_user.username,
            "email":     new_user.email,
            "timestamp": datetime.utcnow().isoformat()
        })

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # check if user is currently locked out
    if _is_locked_out():
        flash(f'Too many failed attempts. Try again later.', 'error')
        return render_template('login.html')

    if request.method == 'POST':
        identifier = request.form.get('username_or_email', '').strip()
        password = request.form.get('password', '')
        remember_me = request.form.get('remember_me')

        # lookup via SQLAlchemy ORM (safe against injection)
        user = User.query.filter(
            or_(User.username == identifier, User.email == identifier)
        ).first()

        if user and user.check_password(password):
            # successful login → reset attempts & lockout
            session.pop('login_attempts', None)
            session.pop('lockout_until', None)

            # set session permanence
            session.permanent = (remember_me == 'on')

            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('dashboard'))

        # failed login: increment attempts
        attempts = session.get('login_attempts', 0) + 1
        session['login_attempts'] = attempts

        if attempts >= MAX_LOGIN_ATTEMPTS:
            # impose lockout window
            until = datetime.utcnow() + timedelta(minutes=LOCKOUT_TIME_MINUTES)
            session['lockout_until'] = until.isoformat()
            flash(f'Too many failed attempts. Try again in {LOCKOUT_TIME_MINUTES} minutes.', 'error')
        else:
            flash('Invalid credentials, please try again.', 'error')

        return redirect(url_for('auth.login'))

    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('auth.login'))
