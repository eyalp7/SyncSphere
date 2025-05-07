# file_management.py
import os
import uuid
from werkzeug.utils import secure_filename
from models import db, File
from config import changes_queue
from datetime import datetime
from config import ALLOWED_EXTENSIONS

class FileManager:
    #Encapsulates file operations.
    def __init__(self, upload_folder):
        """ Initialize FileManager with a directory to store uploaded files. Creates the directory if it doesn't exist. """
        self.upload_folder = upload_folder
        os.makedirs(self.upload_folder, exist_ok=True)

    def allowed_file(self, filename):
        """ Check if the file has an allowed extension. Returns True if extension is in ALLOWED_EXTENSIONS. """
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    def generate_unique_filename(self, filename):
        """ Generate a unique filename using UUID4 and preserve the file extension. """
        ext = filename.rsplit('.', 1)[1] if '.' in filename else ''
        # Combine a random hex string with the original extension
        unique_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
        return unique_name

    def save_file(self, file_storage, user):
        """ Save an uploaded file to disk and create a corresponding DB record. Also updates the user's used_storage and enqueues a sync event. """
        # Validate file presence
        if not file_storage or file_storage.filename == '':
            raise ValueError("No file provided.")
        # Validate extension
        if not self.allowed_file(file_storage.filename):
            raise ValueError("File type not allowed.")

        # Secure the original filename and generate a unique stored name
        original_filename = secure_filename(file_storage.filename)
        unique_filename = self.generate_unique_filename(original_filename)
        file_path = os.path.join(self.upload_folder, unique_filename)

        # Save to disk and measure file size
        file_storage.save(file_path)
        file_size = os.path.getsize(file_path)

        # Enforce user storage quota
        if user.used_storage + file_size > user.storage_quota:
            os.remove(file_path)
            raise ValueError("Storage quota exceeded.")

        # Create DB record for the file
        file_record = File(
            user_id=           user.id,
            stored_filename=   unique_filename,
            original_filename= original_filename,
            file_size=         file_size,
            permissions=       'private'
        )
        db.session.add(file_record)

        # Update user's used storage and commit both changes
        user.used_storage += file_size
        db.session.add(user)
        db.session.commit()

        # Read file content for sync event
        with open(file_path, 'rb') as f:
            content = f.read()

        # Enqueue a file_upload event for synchronization
        changes_queue.put({
            "type":    "file_upload",
            "payload": {
                "id":                 file_record.id,
                "user_id":            file_record.user_id,
                "stored_filename":    file_record.stored_filename,
                "original_filename":  file_record.original_filename,
                "upload_date":        file_record.upload_date.isoformat(),
                "file_size":          file_record.file_size,
                "permissions":        file_record.permissions,
                "content":            content
            },
            "timestamp": datetime.now().isoformat()
        })

        return file_record

    def list_user_files(self, user):
        """ Return a list of File records belonging to the given user. """
        return File.query.filter_by(user_id=user.id).all()

    def get_file_record(self, file_id):
        """ Retrieve a single File record by its ID. Returns None if not found.
        """
        return File.query.get(file_id)

    def delete_file(self, file_record, user, enqueue=True):
        """ Delete a file from disk and remove its DB record. Only the file owner may delete. Enqueues a file_delete sync event. """
        if file_record.user_id != user.id:
            # Prevent unauthorized deletions
            raise PermissionError("You are not authorized to delete this file.")
        # Remove file from disk
        file_path = os.path.join(self.upload_folder, file_record.stored_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        # Remove DB record
        db.session.delete(file_record)
        db.session.commit()

        # Notify other servers of deletion
        if enqueue:
            changes_queue.put({
                "type":    "file_delete",
                "file_id": file_record.id,
                "timestamp": datetime.now().isoformat()
            })
        return True

    def update_permissions(self, file_record, new_permissions, user, enqueue=True):
        """ Change the permission of a file (private or public) Only the owner may change permissions. Enqueues a permission_change sync event. """
        if file_record.user_id != user.id:
            # Prevent unauthorized permission changes
            raise PermissionError("You are not authorized to change permissions for this file.")
        file_record.permissions = new_permissions
        db.session.commit()

        # Notify other servers of permission change
        if enqueue:
            changes_queue.put({
                "type":            "permission_change",
                "file_id":         file_record.id,
                "new_permissions": file_record.permissions,
                "timestamp":       datetime.now().isoformat()
            })
        return file_record

    def is_access_allowed(self, file_record, user):
        """ Check if the given user may access the file. Owners always allowed, otherwise only public files. """
        if file_record.user_id == user.id:
            return True
        return file_record.permissions == 'public'
