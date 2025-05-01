# regional_servers/grand_server.py

import socket
import threading
import json
import time
import ssl
import os

from config import BIND_HOST, GRAND_PORT

# How often (in seconds) to prompt regionals for changes
SYNC_INTERVAL = 60

# History buffer: store last N event batches for reconnects
HISTORY_SIZE = 60
history = []

# Global list of connected regional sockets
clients = []
clients_lock = threading.Lock()
here = os.path.dirname(__file__)
certfile = os.path.join(here, 'server.crt')
keyfile = os.path.join(here, 'server.key')

def send_history(conn):
    """Replay the last HISTORY_SIZE event-lists to this connection."""
    for events in history:
        packet = json.dumps({'type': 'receive', 'events': events}) + '\n'
        try:
            conn.sendall(packet.encode('utf-8'))
        except Exception as e:
            print(f"[GrandServer] Failed to replay history to {conn.getpeername()}: {e}", flush=True)

def accept_loop(server_sock, context):
    """Continuously accept new regional connections and wrap them with TLS."""
    while True:
        try:
            raw_conn, addr = server_sock.accept()
            # Perform TLS handshake on the new connection
            try:
                conn = context.wrap_socket(raw_conn, server_side=True)
                print(f"[GrandServer] Regional connected (TLS): {addr}", flush=True)
            except ssl.SSLError as e:
                print(f"[GrandServer] SSL handshake failed with {addr}: {e}", flush=True)
                raw_conn.close()
                continue

            with clients_lock:
                clients.append(conn)
            # Replay missed events for reconnects
            send_history(conn)
            threading.Thread(target=client_handler, args=(conn,), daemon=True).start()

        except Exception as e:
            print(f"[GrandServer] accept_loop error: {e}", flush=True)
            time.sleep(1)


def client_handler(conn):
    """Read incoming 'changes' messages and rebroadcast them."""
    addr = conn.getpeername()
    f = conn.makefile('r')
    try:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[GrandServer] Invalid JSON from {addr}: {e}", flush=True)
                continue

            mtype = msg.get('type')
            if mtype == 'changes':
                events = msg.get('events', [])
                print(f"[GrandServer] Received {len(events)} events from {addr}", flush=True)
                broadcast(events, exclude=conn)
            else:
                print(f"[GrandServer] Unknown message type from {addr}: {mtype}", flush=True)

    except Exception as e:
        print(f"[GrandServer] Connection error from {addr}: {e}", flush=True)
    finally:
        with clients_lock:
            if conn in clients:
                clients.remove(conn)
        try:
            conn.close()
        except:
            pass
        print(f"[GrandServer] Regional disconnected: {addr}", flush=True)


def sync_loop():
    """Every SYNC_INTERVAL seconds, send 'send' to all live regionals."""
    while True:
        try:
            time.sleep(SYNC_INTERVAL)
            print("[GrandServer] Requesting changes from all regionals...", flush=True)
            packet = json.dumps({'type': 'send'}) + '\n'
            data = packet.encode('utf-8')

            with clients_lock:
                for conn in list(clients):
                    try:
                        conn.sendall(data)
                    except Exception as e:
                        addr = None
                        try:
                            addr = conn.getpeername()
                        except:
                            pass
                        print(f"[GrandServer] Error sending sync request to {addr}: {e}", flush=True)
                        clients.remove(conn)
                        try:
                            conn.close()
                        except:
                            pass

        except Exception as e:
            print(f"[GrandServer] sync_loop error: {e}", flush=True)
            time.sleep(1)


def broadcast(events, exclude=None):
    """Broadcast received events to every regional except the sender and record history."""
    # Record in history buffer
    print(events)
    history.append(events)
    if len(history) > HISTORY_SIZE:
        history.pop(0)

    packet = json.dumps({'type': 'receive', 'events': events}) + '\n'
    data = packet.encode('utf-8')

    with clients_lock:
        for conn in list(clients):
            if conn is exclude:
                continue
            try:
                conn.sendall(data)
            except Exception as e:
                addr = None
                try:
                    addr = conn.getpeername()
                except:
                    pass
                print(f"[GrandServer] Broadcast error to {addr}: {e}", flush=True)
                clients.remove(conn)
                try:
                    conn.close()
                except:
                    pass


def main():
    # Create TCP listening socket
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((BIND_HOST, GRAND_PORT))
    server_sock.listen()
    print(f"[GrandServer] Listening on {BIND_HOST}:{GRAND_PORT}", flush=True)

    # Create a TLS context and load your self-signed cert + key
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=certfile,
                             keyfile=keyfile)

    # Start accepting connections (wrapped in TLS)
    threading.Thread(target=accept_loop, args=(server_sock, context), daemon=True).start()
    # Start the periodic sync loop
    threading.Thread(target=sync_loop, daemon=True).start()

    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[GrandServer] Shutting down.", flush=True)
    finally:
        server_sock.close()


if __name__ == '__main__':
    main()