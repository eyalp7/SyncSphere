import os
import threading
from datetime import timedelta

from flask import Flask, render_template, session, redirect, url_for
from models import db
from auth import auth_bp
from file_management_routes import files_bp
from friend_management_routes import friends_bp

# import the sync client
from sync import connect_to_server

here = os.path.dirname(__file__)
cert = os.path.join(here, 'server.crt')
key  = os.path.join(here, 'server.key')

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
db_file = os.path.join(basedir, 'instance', 'database.db')

app.config['SQLALCHEMY_DATABASE_URI']        = f"sqlite:///{db_file}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key                              = 'your_secret_key'
app.permanent_session_lifetime              = timedelta(days=7)

db.init_app(app)

# register blueprints
app.register_blueprint(auth_bp,    url_prefix='/auth')
app.register_blueprint(files_bp,   url_prefix='/files')
app.register_blueprint(friends_bp, url_prefix='/friends')

@app.route('/')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    from models import User
    from file_management import FileManager

    user = User.query.get(session['user_id'])
    file_manager = FileManager(upload_folder=os.path.join(basedir, 'uploads'))
    files = file_manager.list_user_files(user)

    return render_template(
        'dashboard.html',
        username=user.username,
        files=files,
        current_year=2025
    )

# ensure DB schema exists
with app.app_context():
    db.create_all()

# ─── Launch sync thread exactly once ─────────────────────────────────────
# Only start in the “real” Flask process, not the reloader parent
if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    print("[Sync] Launching background sync thread…", flush=True)
    threading.Thread(target=connect_to_server, daemon=True).start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, use_reloader=False, ssl_context=(cert, key))
