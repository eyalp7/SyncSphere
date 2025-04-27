# file_management.py
import os
import uuid
from werkzeug.utils import secure_filename
from models import db, File
from changes_queue import changes_queue
from datetime import datetime

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

class FileManager:
    def __init__(self, upload_folder):
        self.upload_folder = upload_folder
        os.makedirs(self.upload_folder, exist_ok=True)

    def allowed_file(self, filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    def generate_unique_filename(self, filename):
        ext = filename.rsplit('.', 1)[1] if '.' in filename else ''
        unique_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
        return unique_name

    def save_file(self, file_storage, user):
        if not file_storage or file_storage.filename == '':
            raise ValueError("No file provided.")
        if not self.allowed_file(file_storage.filename):
            raise ValueError("File type not allowed.")

        original_filename = secure_filename(file_storage.filename)
        unique_filename = self.generate_unique_filename(original_filename)
        file_path = os.path.join(self.upload_folder, unique_filename)
        file_storage.save(file_path)
        file_size = os.path.getsize(file_path)

        file_record = File(
            user_id=user.id,
            stored_filename=unique_filename,
            original_filename=original_filename,
            file_size=file_size,
            permissions='private'
        )
        db.session.add(file_record)
        db.session.commit()

        with open(file_path, 'rb') as f:
            content = f.read()

        changes_queue.put({
            "type": "file_upload",
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
        return File.query.filter_by(user_id=user.id).all()

    def get_file_record(self, file_id):
        return File.query.get(file_id)

    def delete_file(self, file_record, user):
        if file_record.user_id != user.id:
            raise PermissionError("You are not authorized to delete this file.")
        file_path = os.path.join(self.upload_folder, file_record.stored_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        db.session.delete(file_record)
        db.session.commit()

        changes_queue.put({
        "type":    "file_delete",
        "file_id": file_record.id,
        "timestamp": datetime.now().isoformat()
    })
        return True

    def update_permissions(self, file_record, new_permissions, user):
        if file_record.user_id != user.id:
            raise PermissionError("You are not authorized to change permissions for this file.")
        file_record.permissions = new_permissions
        db.session.commit()

        changes_queue.put({
        "type":            "permission_change",
        "file_id":         file_record.id,
        "new_permissions": file_record.permissions,
        "timestamp":       datetime.now().isoformat()
    })
        return file_record

    def is_access_allowed(self, file_record, user):
        if file_record.user_id == user.id:
            return True
        if file_record.permissions in ['shared', 'public']:
            return True
        return False
