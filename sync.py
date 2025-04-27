# regional_servers/sync.py

import os
import socket
import json
import base64
import time
from datetime import datetime
from queue import Empty

from config import GRAND_HOST, GRAND_PORT
from changes_queue import changes_queue

# Local upload folder (adjust if needed)
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')


def send_changes(sock):
    """
    Drain local queue, encode any raw file bytes, and send to Grand Server.
    """
    events = []
    while True:
        try:
            change = changes_queue.get_nowait()
        except Empty:
            break

        if change['type'] == 'file_upload':
            p = change['payload'].copy()
            raw = p.pop('content')
            p['content'] = base64.b64encode(raw).decode('utf-8')
            events.append({'type': 'file_upload', 'payload': p, 'timestamp': change['timestamp']})
        else:
            events.append(change)

    if not events:
        return

    packet = {'type': 'changes', 'events': events}
    sock.sendall((json.dumps(packet) + '\n').encode('utf-8'))


def receive_changes(message):
    """
    Apply incoming events from Grand Server inside a Flask app context.
    """
    # import the Flask app instance
    from app import app

    # push a context so db.session, FileManager, etc. work
    with app.app_context():
        # now safe to import your application modules
        from file_management    import FileManager
        from friend_management  import FriendManager
        from models             import db, User, File

        fm = FileManager(upload_folder=UPLOAD_FOLDER)
        fr = FriendManager()

        for ev in message.get('events', []):
            et = ev.get('type')
            try:
                if et == 'file_upload':
                    payload = ev['payload']
                    data = base64.b64decode(payload['content'])
                    dest = os.path.join(UPLOAD_FOLDER, payload['stored_filename'])
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with open(dest, 'wb') as f:
                        f.write(data)

                    rec = File(
                        id=payload['id'],
                        user_id=payload['user_id'],
                        stored_filename=payload['stored_filename'],
                        original_filename=payload['original_filename'],
                        file_size=payload['file_size'],
                        permissions=payload['permissions'],
                        upload_date=datetime.fromisoformat(payload['upload_date'])
                    )
                    db.session.add(rec)
                    db.session.commit()

                elif et == 'file_delete':
                    rec = fm.get_file_record(ev['file_id'])
                    if rec is None:
                        print(f"[Sync] Warn: file_delete skipped, no record for ID {ev['file_id']}", flush=True)
                        continue
                    user = User.query.get(rec.user_id)
                    fm.delete_file(rec, user)

                elif et == 'permission_change':
                    rec = fm.get_file_record(ev['file_id'])
                    if rec is None:
                        print(f"[Sync] Warn: permission_change skipped, no record for ID {ev['file_id']}", flush=True)
                        continue
                    user = User.query.get(rec.user_id)
                    fm.update_permissions(rec, ev['new_permissions'], user)

                elif et == 'user_create':
                    u = User(id=ev['user_id'], username=ev['username'], email=ev['email'])
                    db.session.add(u)
                    db.session.commit()

                elif et == 'friend_request':
                    fr.send_request(
                        User.query.get(ev['from_user']),
                        User.query.get(ev['to_user'])
                    )

                elif et == 'friend_added':
                    fr.respond_request(ev['request_id'], accept=True)

                elif et == 'friend_rejected':
                    fr.respond_request(ev['request_id'], accept=False)

                elif et == 'friend_removed':
                    fr.remove_friend(
                        User.query.get(ev['user_id']),
                        User.query.get(ev['friend_id'])
                    )

                else:
                    print(f"[Sync] Unknown event type: {et}", flush=True)

            except Exception as e:
                print(f"[Sync] Error applying '{et}' event: {e}", flush=True)
                # continue to next event without killing the loop


def sync_changes(sock):
    """
    Read newline-delimited JSON commands from Grand Server and dispatch.
    """
    f = sock.makefile('r')
    for line in f:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        mtype = msg.get('type')
        if mtype == 'send':
            send_changes(sock)
        elif mtype == 'receive':
            receive_changes(msg)

        time.sleep(0)  # yield to other threads

    sock.close()
    print("[Sync] Connection closed", flush=True)


def connect_to_server():
    """
    Establish TCP connection and enter the sync loop.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((GRAND_HOST, GRAND_PORT))
    print("[Sync] Connected to grand server", flush=True)
    sync_changes(sock)
