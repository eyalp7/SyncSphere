from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import User
from friend_management import FriendManager

friends_bp     = Blueprint('friends', __name__)
friend_manager = FriendManager()

def get_current_user():
    user_id = session.get('user_id')
    return User.query.get(user_id) if user_id else None

@friends_bp.route('/send', methods=['GET', 'POST'])
def send_request():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        to_username = request.form.get('to_username')
        to_user = User.query.filter_by(username=to_username).first()
        if not to_user:
            flash("User not found.", "error")
        else:
            try:
                friend_manager.send_request(user, to_user)
                flash("Friend request sent!", "success")
            except ValueError as e:
                flash(str(e), "error")
        return redirect(url_for('friends.send_request'))

    return render_template('send_request.html')

@friends_bp.route('/requests')
def view_requests():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))
    incoming = friend_manager.get_incoming_requests(user)
    return render_template('incoming_requests.html', requests=incoming)

@friends_bp.route('/requests/respond/<int:rq_id>', methods=['POST'])
def respond_request(rq_id):
    user   = get_current_user()
    action = request.form.get('action')  # 'accept' or 'reject'
    try:
        friend_manager.respond_request(rq_id, accept=(action=='accept'))
        flash(f"Request {action}ed.", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for('friends.view_requests'))

@friends_bp.route('/list')
def list_friends():
    user    = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))
    friends = friend_manager.get_friends(user)
    return render_template('friends_list.html', friends=friends)