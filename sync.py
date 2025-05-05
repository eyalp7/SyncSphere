import os
import socket
import json
import base64
import time
import ssl
from datetime import datetime
from queue import Empty

from config import GRAND_HOST, GRAND_PORT, changes_queue, UPLOAD_FOLDER


def send_changes(sock):
    """ Drain the local changes_queue, encode file contents in Base64 when needed, and send a single 'changes' packet to the Grand Server over the socket."""
    events = []
    # Pull all pending events without blocking
    while True:
        try:
            change = changes_queue.get_nowait()
        except Empty:
            break

        # If it's a new file upload, Base64-encode raw bytes for JSON transport
        if change['type'] == 'file_upload':
            p = change['payload'].copy()
            raw = p.pop('content')  # remove binary data from payload
            # encode bytes to UTF-8 string so it can be embedded in JSON
            p['content'] = base64.b64encode(raw).decode('utf-8')
            events.append({
                'type': change['type'],
                'payload': p,
                'timestamp': change['timestamp']
            })
        else:
            # other event types can be sent as-is
            events.append(change)

    # If no events to send, do nothing
    if not events:
        return

    # Build and send the JSON packet, ending with newline for framing
    packet = {'type': 'changes', 'events': events}
    sock.sendall((json.dumps(packet) + '\n').encode('utf-8'))


def receive_changes(message):
    """ Apply incoming events from Grand Server inside a fresh Flask application context. This allows us to modify the database and file system safely."""
    from app import app
    with app.app_context():
        from file_management import FileManager
        from friend_management import FriendManager
        from models import db, User, File

        file_manager = FileManager(upload_folder=UPLOAD_FOLDER)
        friend_manager = FriendManager()

        for ev in message.get('events', []):
            event_type = ev.get('type')
            try:
                if event_type == 'file_upload':
                    # Decode and write file bytes
                    payload = ev['payload']
                    data = base64.b64decode(payload['content'])
                    dest = os.path.join(UPLOAD_FOLDER, payload['stored_filename'])
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with open(dest, 'wb') as f:
                        f.write(data)

                    # Merge into DB (insert or update existing record by ID)
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

                elif event_type == 'file_delete':
                    rec = file_manager.get_file_record(ev['file_id'])
                    if not rec:
                        print(f"[Sync] Warn: no file record for deletion ID {ev['file_id']}", flush=True)
                        continue
                    user = User.query.get(rec.user_id)
                    file_manager.delete_file(rec, user)

                elif event_type == 'permission_change':
                    rec = file_manager.get_file_record(ev['file_id'])
                    if not rec:
                        print(f"[Sync] Warn: no file for permission change ID {ev['file_id']}", flush=True)
                        continue
                    user = User.query.get(rec.user_id)
                    file_manager.update_permissions(rec, ev['new_permissions'], user)

                elif event_type == 'user_create':
                    # Merge new user record, preserves existing if present
                    u = User(
                        id=ev['user_id'],
                        username=ev['username'],
                        email=ev['email'],
                        password_hash=ev.get('password_hash')
                    )
                    db.session.merge(u)
                    db.session.commit()

                elif event_type == 'friend_request':
                    friend_manager.send_request(
                        User.query.get(ev['from_user']),
                        User.query.get(ev['to_user'])
                    )

                elif event_type == 'friend_added':
                    friend_manager.respond_request(ev['request_id'], accept=True)

                elif event_type == 'friend_rejected':
                    friend_manager.respond_request(ev['request_id'], accept=False)

                elif event_type == 'friend_removed':
                    friend_manager.remove_friend(
                        User.query.get(ev['user_id']),
                        User.query.get(ev['friend_id'])
                    )

                else:
                    # Unknown event type — log for debugging
                    print(f"[Sync] Unknown event type: {event_type}", flush=True)

            except Exception as e:
                # Roll back any partial DB changes on error
                db.session.rollback()
                print(f"[Sync] Error applying '{event_type}' event: {e}", flush=True)


def sync_changes(sock):
    """ Read newline-delimited JSON commands from Grand Server and dispatch to send_changes or receive_changes handlers."""
    buffer = sock.makefile('r')  # wrap socket in file-like object for line reads
    for line in buffer:
        try:
            received_message = json.loads(line)
        except json.JSONDecodeError:
            continue

        message_type = received_message.get('type')
        if message_type == 'send':
            send_changes(sock)
        elif message_type == 'receive':
            receive_changes(received_message)

        time.sleep(0)  # yield to other threads

    # When connection closes, clean up
    sock.close()
    print("[Sync] Connection closed", flush=True)


def connect_to_server():
    """ Establish a TLS-wrapped TCP connection to the Grand Server, then enter the sync loop."""
    # Create SSL context for client with no verification (dev only)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock = context.wrap_socket(raw_sock, server_hostname=GRAND_HOST)

    sock.connect((GRAND_HOST, GRAND_PORT))
    print("[Sync] Connected to grand server", flush=True)
    sync_changes(sock)
