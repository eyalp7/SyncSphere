# regional_servers/sync.py

import os
import socket
import json
import base64
import time
import ssl
from datetime import datetime
from queue import Empty

from config import GRAND_HOST, GRAND_PORT
from changes_queue import changes_queue

# Adjust this path if your uploads folder is elsewhere
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')


def send_changes(sock):
    """Drain local queue, base64‐encode file bytes if needed, and send to Grand Server."""
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
    Apply events from Grand Server inside a fresh Flask app context.
    """
    from app import app
    with app.app_context():
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
                    # 1) write file bytes to disk
                    data = base64.b64decode(payload['content'])
                    dest = os.path.join(UPLOAD_FOLDER, payload['stored_filename'])
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with open(dest, 'wb') as f:
                        f.write(data)

                    # 2) merge into DB (insert or update)
                    rec = File(
                        id=payload['id'],
                        user_id=payload['user_id'],
                        stored_filename=payload['stored_filename'],
                        original_filename=payload['original_filename'],
                        file_size=payload['file_size'],
                        permissions=payload['permissions'],
                        upload_date=datetime.fromisoformat(payload['upload_date'])
                    )
                    db.session.merge(rec)
                    db.session.commit()

                elif et == 'file_delete':
                    rec = fm.get_file_record(ev['file_id'])
                    if not rec:
                        print(f"[Sync] Warn: no file record for deletion ID {ev['file_id']}", flush=True)
                        continue
                    user = User.query.get(rec.user_id)
                    fm.delete_file(rec, user)

                elif et == 'permission_change':
                    rec = fm.get_file_record(ev['file_id'])
                    if not rec:
                        print(f"[Sync] Warn: no file for permission change ID {ev['file_id']}", flush=True)
                        continue
                    user = User.query.get(rec.user_id)
                    fm.update_permissions(rec, ev['new_permissions'], user)

                elif et == 'user_create':
                    u = User(
                        id=ev['user_id'],
                        username=ev['username'],
                        email=ev['email'],
                        password_hash=ev.get('password_hash')
                    )
                    db.session.merge(u)
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
                db.session.rollback()
                print(f"[Sync] Error applying '{et}' event: {e}", flush=True)


def sync_changes(sock):
    """
    Read newline-delimited JSON commands from Grand Server and dispatch handlers.
    """
    buffer = sock.makefile('r')
    for line in buffer:
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

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock = context.wrap_socket(raw_sock, server_hostname=GRAND_HOST)

    sock.connect((GRAND_HOST, GRAND_PORT))
    print("[Sync] Connected to grand server", flush=True)
    sync_changes(sock)