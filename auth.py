# auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if not username or not email or not password:
            flash('Please fill in all fields!', 'error')
            return redirect(url_for('auth.register'))

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('Username or Email already exists!', 'error')
            return redirect(url_for('auth.register'))

        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('username_or_email')
        password = request.form.get('password')
        # Debug: Print the value of the remember me checkbox
        remember_me = request.form.get('remember_me')
        print("Remember me checkbox value:", remember_me)  # Check console output

        user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()

        if user and user.check_password(password):
            # Set the session permanence based on the remember_me checkbox
            if remember_me == 'on':
                session.permanent = True
            else:
                session.permanent = False

            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials, please try again.', 'error')
            return redirect(url_for('auth.login'))
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('auth.login'))
