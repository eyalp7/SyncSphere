import os
import threading
from datetime import timedelta

from flask import Flask, render_template, session, redirect, url_for, flash
from flask_wtf import CSRFProtect

from models import db
from auth import auth_bp
from file_management_routes import files_bp
from friend_management_routes import friends_bp
from config import certfile, keyfile, basedir, db_file, secret_key
from sync import connect_to_server

app = Flask(__name__)

# Secret key for signing session cookies and CSRF tokens
app.config['SECRET_KEY'] = secret_key

# SQLite database URI (absolute path to file)
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_file}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # disable event system to save memory

app.config.update({
    # Only send session cookie over HTTPS
    'SESSION_COOKIE_SECURE':   True,
    # Prevent JavaScript access to the cookie
    'SESSION_COOKIE_HTTPONLY': True,
    # Mitigate CSRF by restricting cross-site sending of cookies
    'SESSION_COOKIE_SAMESITE': 'Lax',
    # Lifetime of a “permanent” session
    'PERMANENT_SESSION_LIFETIME': timedelta(days=7)
})

# Initialize the SQLAlchemy extension
db.init_app(app)

# Wrap the app in Flask-WTF's CSRFProtect to auto-validate tokens on all POST forms
csrf = CSRFProtect(app)

# Authentication routes: /auth/...
app.register_blueprint(auth_bp, url_prefix='/auth')
# File management routes: /files/...
app.register_blueprint(files_bp, url_prefix='/files')
# Friend management routes: /friends/...
app.register_blueprint(friends_bp, url_prefix='/friends')

@app.route('/')
def dashboard():
    # 1) Ensure we have a user_id in session
    uid = session.get('user_id')
    if not uid:
        return redirect(url_for('auth.login'))

    # Lazy imports to avoid circular dependencies
    from models import User
    from file_management import FileManager

    # 2) Load current user from DB using Session.get() to avoid legacy warning
    user = db.session.get(User, uid)
    if user is None:
        # Stale or invalid session → clear and force re-login
        session.clear()
        flash("Please log in again.", "error")
        return redirect(url_for('auth.login'))

    # 3) Instantiate FileManager and fetch the user's files
    file_manager = FileManager(upload_folder=os.path.join(basedir, 'uploads'))
    files = file_manager.list_user_files(user)

    # 4) Render the dashboard template with user data
    return render_template(
        'dashboard.html',
        username=user.username,
        files=files,
        current_user=user,
    )
if __name__ == '__main__':
    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()

    # Launch the background sync thread exactly once
    print("[Sync] Launching background sync thread…", flush=True)
    threading.Thread(target=connect_to_server, daemon=True).start()

    # Start the Flask HTTPS server (self-signed cert for dev)
    app.run(
        host='0.0.0.0',
        debug=False,               # disable debugger in production
        ssl_context=(certfile, keyfile)
    )
