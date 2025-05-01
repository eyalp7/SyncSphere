from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import User
from friend_management import FriendManager
from file_management import FileManager

# Blueprint for friend-related routes under /friends
friends_bp     = Blueprint('friends', __name__)
# Manager instances for business logic
friend_manager = FriendManager()
file_manager   = FileManager(upload_folder='uploads')


def get_current_user():
    """ Retrieve the logged-in user from the session. Returns None if no user is logged in. """
    user_id = session.get('user_id')
    return User.query.get(user_id) if user_id else None


@friends_bp.route('/requests', methods=['GET', 'POST'])
def view_requests():
    """ GET:  Show incoming & outgoing friend requests, and a form to send new ones. POST: Handle submission of a new friend request by username. """
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))

    # Handle new request submission
    if request.method == 'POST' and 'to_username' in request.form:
        to_username = request.form['to_username']
        to_user = User.query.filter_by(username=to_username).first()
        if not to_user:
            flash("User not found.", "error")
        else:
            try:
                friend_manager.send_request(user, to_user)
                flash("Friend request sent!", "success")
            except ValueError as e:
                flash(str(e), "error")
        return redirect(url_for('friends.view_requests'))

    # Build lists for template
    raw_in = friend_manager.get_incoming_requests(user)
    incoming = [
        {'req': fr, 'sender': User.query.get(fr.from_user_id)}
        for fr in raw_in
    ]

    raw_out = friend_manager.get_outgoing_requests(user)
    outgoing = [ User.query.get(fr.to_user_id) for fr in raw_out ]

    return render_template(
        'incoming_requests.html',
        incoming=incoming,
        outgoing=outgoing
    )


@friends_bp.route('/requests/respond/<int:rq_id>', methods=['POST'])
def respond_request(rq_id):
    """ Handle acceptance or rejection of a friend request. """
    user   = get_current_user()
    action = request.form.get('action')
    try:
        friend_manager.respond_request(rq_id, accept=(action == 'accept'))
        flash(f"Request {action}ed.", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for('friends.view_requests'))


@friends_bp.route('/list')
def list_friends():
    """ Display the current user's friend list. """
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))
    friends = friend_manager.get_friends(user)
    return render_template('friends_list.html', friends=friends)


@friends_bp.route('/remove/<username>', methods=['POST'])
def remove(username):
    """ Remove an existing friendship. """
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))

    to_user = User.query.filter_by(username=username).first()
    if not to_user:
        flash("User not found.", "error")
    else:
        try:
            friend_manager.remove_friend(user, to_user)
            flash("Friend removed.", "success")
        except ValueError as e:
            flash(str(e), "error")

    return redirect(url_for('friends.list_friends'))


@friends_bp.route('/<username>/files')
def view_friend_files(username):
    """ View files shared by a specific friend. Only files with 'public' permission or owned by the friend are shown.
    """
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))

    friend = User.query.filter_by(username=username).first()
    if not friend:
        flash("User not found.", "error")
        return redirect(url_for('friends.list_friends'))

    all_files     = file_manager.list_user_files(friend)
    # Filter out files the current user isn't allowed to see
    allowed_files = [f for f in all_files if file_manager.is_access_allowed(f, user)]

    return render_template(
        'friends_files.html',
        files=allowed_files,
        friend=friend
    )
