# file_management_routes.py
from flask import Blueprint, request, render_template, flash, redirect, url_for, send_from_directory, session
from models import db, User
from file_management import FileManager

files_bp = Blueprint('files', __name__)
file_manager = FileManager(upload_folder='uploads')

def get_current_user():
    user_id = session.get('user_id')
    if user_id:
        from models import User
        return User.query.get(user_id)
    return None

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
            # Redirect to the dashboard instead of a separate upload page
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(str(e), "error")
            return redirect(url_for('dashboard'))
    # If GET is needed, you may remove this or also redirect to dashboard
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
    return send_from_directory(file_manager.upload_folder,
                               file_record.stored_filename,
                               as_attachment=True,
                               download_name=file_record.original_filename)

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
