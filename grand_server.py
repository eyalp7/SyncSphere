# regional_servers/grand_server.py

import socket
import threading
import json
import time
import ssl

from config import BIND_HOST, GRAND_PORT, certfile, keyfile

# How often (in seconds) to prompt regionals for changes
SYNC_INTERVAL = 30  # 1 sync every 30 seconds

# We want to keep all batches from the last 5 sync intervals (5×SYNC_INTERVAL seconds)
HISTORY_WINDOW = SYNC_INTERVAL * 5

# history holds dicts {"ts": timestamp, "events": […]}
history = []

# Global list of connected regional sockets
clients = []
clients_lock = threading.Lock()  # ensure one thread at a time touches clients list


def send_history(conn):
    """
    Replay every batch of events from the last HISTORY_WINDOW seconds
    to this newly connected regional_server.
    """
    cutoff = time.time() - HISTORY_WINDOW
    # send each batch whose timestamp is within the window
    for entry in history:
        if entry["ts"] < cutoff:
            continue
        packet = json.dumps({'type': 'receive', 'events': entry["events"]}) + '\n'
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

            # add to clients under lock
            with clients_lock:
                clients.append(conn)

            # replay missed-history batches
            send_history(conn)

            # start handler thread
            threading.Thread(target=client_handler, args=(conn,), daemon=True).start()

        except Exception as e:
            print(f"[GrandServer] accept_loop error: {e}", flush=True)
            time.sleep(1)


def client_handler(conn):
    """Read incoming 'changes' messages and rebroadcast them."""
    addr = conn.getpeername()
    f = conn.makefile('r')  # treat socket as file for line-based reading
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
        # remove disconnected client
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
    """
    Broadcast received events to every regional except the sender,
    and record each batch with a timestamp for history-window replay.
    """
    # record this batch with the current time
    history.append({
        "ts": time.time(),
        "events": events
    })
    # purge any entries older than HISTORY_WINDOW
    cutoff = time.time() - HISTORY_WINDOW
    history[:] = [h for h in history if h["ts"] >= cutoff]

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
    # allow quick reuse after restart
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((BIND_HOST, GRAND_PORT))
    server_sock.listen()
    print(f"[GrandServer] Listening on {BIND_HOST}:{GRAND_PORT}", flush=True)

    # Create TLS context and load certificate/key
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)

    # start accept and sync loops in background threads
    threading.Thread(target=accept_loop, args=(server_sock, context), daemon=True).start()
    threading.Thread(target=sync_loop, daemon=True).start()

    try:
        # keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[GrandServer] Shutting down.", flush=True)
    finally:
        server_sock.close()


if __name__ == '__main__':
    main()
