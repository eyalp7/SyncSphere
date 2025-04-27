import socket
import threading
import json
import time

from config import GRAND_HOST, GRAND_PORT

# Interval (in seconds) at which to request changes from regionals
SYNC_INTERVAL = 60  # 1 minute

# Global list of connected regional sockets
clients = []
clients_lock = threading.Lock()


def accept_loop(server_sock):
    """
    Accept new regional connections and start a handler thread for each.
    """
    while True:
        conn, addr = server_sock.accept()
        print(f"[GrandServer] Regional connected: {addr}")
        with clients_lock:
            clients.append(conn)
        threading.Thread(target=client_handler, args=(conn,), daemon=True).start()


def client_handler(conn):
    """
    Read newline-delimited JSON messages from a regional and rebroadcast valid events.
    """
    # Wrap socket in a text-mode file to read lines
    f = conn.makefile('r')
    try:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[GrandServer] Invalid JSON: {e} -- {line}")
                continue

            mtype = msg.get('type')
            if mtype == 'changes':
                events = msg.get('events', [])
                print(f"[GrandServer] Received {len(events)} events")
                broadcast(events, exclude=conn)
            else:
                print(f"[GrandServer] Unknown message type: {mtype}")
    except Exception as e:
        print(f"[GrandServer] Connection error: {e}")
    finally:
        with clients_lock:
            if conn in clients:
                clients.remove(conn)
        conn.close()
        print("[GrandServer] Regional disconnected")


def sync_loop():
    """
    Every SYNC_INTERVAL seconds, prompt all regionals to send queued changes.
    """
    while True:
        time.sleep(SYNC_INTERVAL)
        print("[GrandServer] Requesting changes from all regionals...")
        packet = json.dumps({'type': 'send'}) + '\n'
        data = packet.encode('utf-8')
        with clients_lock:
            for conn in list(clients):
                try:
                    conn.sendall(data)
                except Exception as e:
                    print(f"[GrandServer] Error sending sync request: {e}")


def broadcast(events, exclude=None):
    """
    Broadcast a list of events to every regional except `exclude`.
    """
    packet = json.dumps({'type': 'receive', 'events': events}) + '\n'
    data = packet.encode('utf-8')
    with clients_lock:
        for conn in list(clients):
            if conn is exclude:
                continue
            try:
                conn.sendall(data)
            except Exception as e:
                print(f"[GrandServer] Broadcast error: {e}")


def main():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((GRAND_HOST, GRAND_PORT))
    server_sock.listen()
    print(f"[GrandServer] Listening on {GRAND_HOST}:{GRAND_PORT}")

    # Start accept and sync threads
    threading.Thread(target=accept_loop, args=(server_sock,), daemon=True).start()
    threading.Thread(target=sync_loop, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[GrandServer] Shutting down.")
    finally:
        server_sock.close()


if __name__ == '__main__':
    main()
