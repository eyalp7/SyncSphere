# file_management_routes.py

from flask import Blueprint, request, flash, redirect, url_for, send_from_directory, session
from models import User
from file_management import FileManager
import os

files_bp = Blueprint('files', __name__)
basedir = os.path.abspath(os.path.dirname(__file__))  # ends in …/regional_server
upload_dir = os.path.join(basedir, 'uploads')

file_manager = FileManager(upload_folder=upload_dir)

def get_current_user():
    user_id = session.get('user_id')
    return User.query.get(user_id) if user_id else None

@files_bp.route('/upload', methods=['GET', 'POST'])
def upload():
    user = get_current_user()
    if not user:
        flash("Please log in first.", "error")
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        if 'file' not in request.files:
            flash("No file part in the request.", "error")
            return redirect(url_for('dashboard'))
        file_storage = request.files['file']
        try:
            file_manager.save_file(file_storage, user)
            flash("File uploaded successfully!", "success")
        except Exception as e:
            flash(str(e), "error")
        return redirect(url_for('dashboard'))

    return redirect(url_for('dashboard'))

@files_bp.route('/download/<int:file_id>')
def download(file_id):
    user = get_current_user()
    file_record = file_manager.get_file_record(file_id)
    if not file_record:
        flash("File not found.", "error")
        return redirect(url_for('dashboard'))
    if not file_manager.is_access_allowed(file_record, user):
        flash("Access not allowed.", "error")
        return redirect(url_for('dashboard'))

    return send_from_directory(
        file_manager.upload_folder,
        file_record.stored_filename,
        as_attachment=True,
        download_name=file_record.original_filename
    )

@files_bp.route('/delete/<int:file_id>', methods=['POST'])
def delete(file_id):
    user = get_current_user()
    file_record = file_manager.get_file_record(file_id)
    if not file_record:
        flash("File not found.", "error")
        return redirect(url_for('dashboard'))
    try:
        file_manager.delete_file(file_record, user)
        flash("File deleted successfully.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for('dashboard'))

# ──────────────────────────────────────────────────
# Inline Permissions Update (same dashboard page)
# ──────────────────────────────────────────────────
@files_bp.route('/permissions/<int:file_id>', methods=['POST'])
def change_permissions(file_id):
    user = get_current_user()
    if not user:
        flash("Please log in first.", "error")
        return redirect(url_for('auth.login'))

    file_record = file_manager.get_file_record(file_id)
    if not file_record:
        flash("File not found.", "error")
        return redirect(url_for('dashboard'))
    # Ensure only owner can change permissions
    if file_record.user_id != user.id:
        flash("Access not allowed.", "error")
        return redirect(url_for('dashboard'))

    # Get new permission from form
    new_perm = request.form.get('permissions')
    try:
        file_manager.update_permissions(file_record, new_perm, user)
        flash("Permissions updated!", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for('dashboard'))
