from flask import Blueprint, request, flash, redirect, url_for, send_from_directory, session
from models import User
from file_management import FileManager
import os

# Blueprint for file operations, all routes under /files
files_bp = Blueprint('files', __name__)

# Determine absolute path to the uploads directory
basedir    = os.path.abspath(os.path.dirname(__file__))
upload_dir = os.path.join(basedir, 'uploads')

# Instantiate FileManager with the upload folder path
file_manager = FileManager(upload_folder=upload_dir)


def get_current_user():
    """ Helper to retrieve the logged-in User from session. Returns None if no valid user_id in session. """
    user_id = session.get('user_id')
    return User.query.get(user_id) if user_id else None


@files_bp.route('/upload', methods=['POST'])
def upload():
    """ Handle file upload: """
    user = get_current_user()
    if not user:
        flash("Please log in first.", "error")
        return redirect(url_for('auth.login'))

    # Get the FileStorage object from the form
    file_storage = request.files.get('file')
    if not file_storage or not file_storage.filename:
        flash("No file selected for upload.", "error")
        return redirect(url_for('dashboard'))

    try:
        # Attempt to save file; may flash quota or type errors internally
        file_manager.save_file(file_storage, user)
        flash("File uploaded successfully!", "success")
    except ValueError as e:
        # Known validation error from FileManager
        flash(str(e), "error")
    except Exception:
        # Unexpected error
        flash("An unexpected error occurred while uploading.", "error")

    return redirect(url_for('dashboard'))


@files_bp.route('/download/<int:file_id>')
def download(file_id):
    """ Serve a file download if the user has permission. """
    user = get_current_user()
    file_record = file_manager.get_file_record(file_id)
    if not file_record:
        flash("File not found.", "error")
        return redirect(url_for('dashboard'))

    # Ensure user owns the file or it's public
    if not file_manager.is_access_allowed(file_record, user):
        flash("Access not allowed.", "error")
        return redirect(url_for('dashboard'))

    # Send the stored file under its original filename
    return send_from_directory(
        file_manager.upload_folder,
        file_record.stored_filename,
        as_attachment=True,
        download_name=file_record.original_filename
    )


@files_bp.route('/delete/<int:file_id>', methods=['POST'])
def delete(file_id):
    """ Delete a file record and its physical file. """
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


@files_bp.route('/permissions/<int:file_id>', methods=['POST'])
def change_permissions(file_id):
    """Update a file's access permissions (private or public). """
    user = get_current_user()
    if not user:
        flash("Please log in first.", "error")
        return redirect(url_for('auth.login'))

    file_record = file_manager.get_file_record(file_id)
    if not file_record:
        flash("File not found.", "error")
        return redirect(url_for('dashboard'))

    # Only the owner can change permissions
    if file_record.user_id != user.id:
        flash("Access not allowed.", "error")
        return redirect(url_for('dashboard'))

    new_perm = request.form.get('permissions')
    try:
        file_manager.update_permissions(file_record, new_perm, user)
        flash("Permissions updated!", "success")
    except Exception as e:
        flash(str(e), "error")

    return redirect(url_for('dashboard'))
