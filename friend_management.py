from models import db, User, FriendRequest, Friendship

class FriendManager:
    def send_request(self, from_user, to_user):
        if from_user.id == to_user.id:
            raise ValueError("Cannot friend yourself.")
        existing = FriendRequest.query.filter_by(
            from_user_id=from_user.id, to_user_id=to_user.id
        ).first()
        if existing:
            raise ValueError("Friend request already sent.")
        fr = FriendRequest(from_user_id=from_user.id, to_user_id=to_user.id)
        db.session.add(fr)
        db.session.commit()
        return fr

    def get_incoming_requests(self, user):
        return FriendRequest.query.filter_by(
            to_user_id=user.id, status='pending'
        ).all()

    def respond_request(self, request_id, accept=True):
        fr = FriendRequest.query.get(request_id)
        if not fr:
            raise ValueError("Friend request not found.")
        fr.status = 'accepted' if accept else 'rejected'
        if accept:
            db.session.add(Friendship(user_id=fr.from_user_id, friend_id=fr.to_user_id))
            db.session.add(Friendship(user_id=fr.to_user_id,   friend_id=fr.from_user_id))
        db.session.commit()
        return fr

    def get_friends(self, user):
        fs = Friendship.query.filter_by(user_id=user.id).all()
        return [User.query.get(f.friend_id) for f in fs]