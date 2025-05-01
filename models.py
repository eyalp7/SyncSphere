from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    #A class that represents a user in the system.
    id = db.Column(db.Integer, primary_key=True) #The id of the user.
    username = db.Column(db.String(80), unique=True, nullable=False) #The username.
    email = db.Column(db.String(120), unique=True, nullable=False) #The email of the user.
    password_hash = db.Column(db.String(128), nullable=False) #The hashed password of the user.
    created_at = db.Column(db.DateTime, default=datetime.now) #The creation date of the user.
    used_storage  = db.Column(db.Integer, nullable=False, default=0) #The used storage of the user.
    storage_quota = db.Column(db.Integer, nullable=False, default=1073741824) #The max storage of the user.

    def set_password(self, password):
            """Generating the hash value of the password."""
            self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Checking if the password is the same as the user's password. """
        return check_password_hash(self.password_hash, password)

class File(db.Model):
    #Represents the metadata of a file in the system.
    id = db.Column(db.Integer, primary_key=True) #The id of the file
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) #The id of the file's owner.
    stored_filename = db.Column(db.String(128), nullable=False) #The name of the file in the file system.
    original_filename = db.Column(db.String(128), nullable=False) #The original name of the file.
    upload_date = db.Column(db.DateTime, default=datetime.now) #The creation date of the file.
    file_size = db.Column(db.Integer) #The file's size.
    permissions = db.Column(db.String(32), default='private') #The file's viewing permission.

class FriendRequest(db.Model):
    #Represents a friend request in the system.
    id = db.Column(db.Integer, primary_key=True) #The id of the request.
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) #The id of the sender.
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) #The id of the receiver.
    status = db.Column(db.String(16), default='pending')  #The status of the friend request('pending', 'accepted', 'rejected')
    created_at = db.Column(db.DateTime, default=datetime.now) #The creation date of the friend request.

class Friendship(db.Model):
    #Represents a friendship in the system.
    id = db.Column(db.Integer, primary_key=True) #The id of the friendship.
    user_id  = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) #The id of one of the user.
    friend_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) #The id of the other user.
    created_at = db.Column(db.DateTime, default=datetime.now) #The creation date of the friendship.