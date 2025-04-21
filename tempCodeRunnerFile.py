# app.py
from flask import Flask, render_template, session, redirect, url_for
from datetime import timedelta
from models import db
from auth import auth_bp
from file_management_routes import files_bp

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'  # Replace with your strong secret key

# Set session lifetime to 7 days for persistent login
app.permanent_session_lifetime = timedelta(days=7)

db.init_app(app)

# Register blueprints
app.register_blueprint(auth_bp)  # Authentication routes
app.register_blueprint(files_bp, url_prefix='/files')  # File management routes

@app.route('/')
def home():
    return redirect(url_for('auth.login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    from models import User
    user = User.query.get(session['user_id'])
    from file_management import FileManager
    file_manager = FileManager('uploads')
    files = file_manager.list_user_files(user)
    return render_template('dashboard.html', username=user.username, files=files, current_year=2025)

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
