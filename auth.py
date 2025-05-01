from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_
from models import db, User
from config import changes_queue
from datetime import datetime, timedelta

# Create a Blueprint for all auth-related routes (register, login, logout)
auth_bp = Blueprint('auth', __name__)

# Lockout policy: max failed attempts before temporary block
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_TIME_MINUTES = 15

def _is_locked_out():
    """ Check if the current session is under lockout. Returns True if lockout hasn’t expired; otherwise clears lockout state."""
    lockout_until = session.get('lockout_until')
    if lockout_until and datetime.fromisoformat(lockout_until) > datetime.utcnow():
        return True
    # Lockout expired or not set → remove any stale counters
    session.pop('lockout_until', None)
    session.pop('login_attempts', None)
    return False

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """ Handle user registration."""
    if request.method == 'POST':
        session.clear()  # Prevent session fixation attacks

        username = request.form['username'].strip()
        email    = request.form['email'].strip()
        password = request.form['password']

        # Basic input validation
        if not username or not email or not password:
            flash('Please fill in all fields!', 'error')
            return redirect(url_for('auth.register'))

        # Check for existing user by username OR email (safe ORM filter, avoids SQLi)
        existing = User.query.filter(
            or_(User.username == username, User.email == email)
        ).first()
        if existing:
            flash('Username or Email already exists!', 'error')
            return redirect(url_for('auth.register'))

        # Create and hash the new user's password
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        # Notify other regional servers of the new user
        changes_queue.put({
            "type":      "user_create",
            "user_id":   new_user.id,
            "username":  new_user.username,
            "email":     new_user.email,
            "timestamp": datetime.utcnow().isoformat()
        })

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    # GET request → render form template
    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """ Handle user login. """
    if _is_locked_out():
        flash('Too many failed attempts. Try again later.', 'error')
        # Render the login template without redirect to preserve lockout message
        return render_template('login.html')

    if request.method == 'POST':
        session.clear()  # Prevent session fixation on every login attempt

        identifier = request.form['username_or_email'].strip()
        password   = request.form['password']
        remember   = 'remember_me' in request.form  # Checkbox presence

        # Lookup by username OR email using safe ORM parameter binding
        user = User.query.filter(
            or_(User.username == identifier, User.email == identifier)
        ).first()

        # Verify password using Werkzeug’s constant-time check
        if user and user.check_password(password):
            # Reset failed-attempt counters on success
            session.pop('login_attempts', None)
            session.pop('lockout_until', None)
            # Store minimal user info in session
            session['user_id']   = user.id
            session['username']  = user.username
            session.permanent    = remember  # honor “Remember Me”
            return redirect(url_for('dashboard'))

        # Failed login: increment counter
        attempts = session.get('login_attempts', 0) + 1
        session['login_attempts'] = attempts

        # If too many fails, impose lockout window
        if attempts >= MAX_LOGIN_ATTEMPTS:
            until = datetime.utcnow() + timedelta(minutes=LOCKOUT_TIME_MINUTES)
            session['lockout_until'] = until.isoformat()
            flash(f'Too many failed attempts. Try again in {LOCKOUT_TIME_MINUTES} minutes.', 'error')
        else:
            flash('Invalid credentials, please try again.', 'error')

        return redirect(url_for('auth.login'))

    # GET request → render the login form
    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    """ Log the user out by clearing the session and redirecting to login."""
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('auth.login'))
