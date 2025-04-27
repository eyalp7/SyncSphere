from models import db, User, FriendRequest, Friendship
from changes_queue import changes_queue
from datetime import datetime

class FriendManager:
    def send_request(self, from_user, to_user):
        if from_user.id == to_user.id:
            raise ValueError("Cannot friend yourself.")

        # Block if there's already a pending request in either direction
        existing = FriendRequest.query.filter_by(
            from_user_id=from_user.id,
            to_user_id=to_user.id,
            status='pending'
        ).first()
        if not existing:
            existing = FriendRequest.query.filter_by(
                from_user_id=to_user.id,
                to_user_id=from_user.id,
                status='pending'
            ).first()
        if existing:
            raise ValueError("Friend request already pending.")

        # Block if users are already friends
        fri = Friendship.query.filter_by(user_id=from_user.id, friend_id=to_user.id).first()
        if not fri:
            fri = Friendship.query.filter_by(user_id=to_user.id, friend_id=from_user.id).first()
        if fri:
            raise ValueError("You are already friends.")

        fr = FriendRequest(
            from_user_id=from_user.id,
            to_user_id=to_user.id
        )
        db.session.add(fr)
        db.session.commit()

        changes_queue.put({
            "type":       "friend_request",
            "request_id": fr.id,
            "from_user":  fr.from_user_id,
            "to_user":    fr.to_user_id,
            "timestamp":  datetime.now().isoformat()
        })
        return fr

    def get_incoming_requests(self, user):
        return FriendRequest.query.filter_by(
            to_user_id=user.id,
            status='pending'
        ).all()

    def get_outgoing_requests(self, user):
        return FriendRequest.query.filter_by(
            from_user_id=user.id,
            status='pending'
        ).all()

    def respond_request(self, request_id, accept=True):
        fr = FriendRequest.query.get(request_id)
        if not fr:
            raise ValueError("Friend request not found.")
        fr.status = 'accepted' if accept else 'rejected'
        if accept:
            # create reciprocal friendships
            db.session.add(Friendship(user_id=fr.from_user_id, friend_id=fr.to_user_id))
            db.session.add(Friendship(user_id=fr.to_user_id,   friend_id=fr.from_user_id))
        db.session.commit()

        if accept:
            # Enqueue new friendship event
            changes_queue.put({
                "type":      "friend_added",
                "user_id":   fr.from_user_id,
                "friend_id": fr.to_user_id,
                "timestamp": datetime.now().isoformat()
            })
        else:
            # Optionally enqueue a rejection event
            changes_queue.put({
                "type":      "friend_rejected",
                "request_id": fr.id,
                "from_user":  fr.from_user_id,
                "to_user":    fr.to_user_id,
                "timestamp":  datetime.now().isoformat()
            })
        return fr

    def get_friends(self, user):
        fs = Friendship.query.filter_by(user_id=user.id).all()
        return [User.query.get(f.friend_id) for f in fs]

    def remove_friend(self, user, to_user):
        f1 = Friendship.query.filter_by(user_id=user.id,    friend_id=to_user.id).first()
        f2 = Friendship.query.filter_by(user_id=to_user.id, friend_id=user.id).first()
        if not f1 and not f2:
            raise ValueError("Friendship not found.")
        if f1:
            db.session.delete(f1)
        if f2:
            db.session.delete(f2)
        db.session.commit()

        changes_queue.put({
            "type":      "friend_removed",
            "user_id":   user.id,
            "friend_id": to_user.id,
            "timestamp": datetime.now().isoformat()
        })
        return True
