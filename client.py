import socket
import os
from protocol import *

# =======================================
#  Config
# =======================================
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8080
CLIENT_DIR  = "client/"   # folder of client files to upload/download


# =======================================
#  Handshake
# =======================================

def handshake(sock):
    """
    Perform 3-way handshake with server.
    Returns ISN on success, None on failure.
    """
    isn = generate_isn()

    for attempt in range(1, MAX_RETRIES + 1):
        sock.sendto(build_syn(isn), (SERVER_HOST, SERVER_PORT))
        print(f"[SYN] Sent ISN={isn} (attempt {attempt})")

        try:
            sock.settimeout(TIMEOUT)
            raw, _ = sock.recvfrom(4096)
            pkt = parse_packet(raw)

            if pkt["type"] == ERROR:
                print(f"[ERROR] Server responded: error_type={pkt['error_type']}, retrying...")
                continue

            if pkt["type"] == SYN_ACK:
                print(f"[SYN-ACK] Received SEQ={pkt['seq']}, sending ACK...")
                sock.sendto(build_ack(pkt["seq"]), (SERVER_HOST, SERVER_PORT))
                print(f"[ACK] Sent, session established!")
                return isn

        except socket.timeout:
            print(f"[TIMEOUT] No response from server (attempt {attempt})")

    print("[FAIL] Handshake failed after max retries.")
    return None


# =======================================
#  Download (GET)
# =======================================

def download(sock, filename, seq):
    """
    Request and receive a file from the server.
    Saves to CLIENT_DIR.
    Returns updated seq on success, None on failure.
    """
    # Send REQUEST
    sock.sendto(build_request_get(filename), (SERVER_HOST, SERVER_PORT))
    print(f"[REQUEST] GET {filename}")

    # Wait for ACK (filesize, OK) or ERROR
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            sock.settimeout(TIMEOUT)
            raw, _ = sock.recvfrom(4096)
            pkt = parse_packet(raw)

            if pkt["type"] == ERROR:
                if pkt["error_type"] == ERR_NOT_FOUND:
                    print(f"[ERROR] File not found on server.")
                else:
                    print(f"[ERROR] Server error type={pkt['error_type']}")
                return None

            if pkt["type"] == ACK and pkt["subtype"] == "filesize":
                filesize = pkt["filesize"]
                print(f"[ACK] Server confirmed file size={filesize} bytes")
                break

        except socket.timeout:
            print(f"[TIMEOUT] Waiting for server response (attempt {attempt})")
            sock.sendto(build_request_get(filename), (SERVER_HOST, SERVER_PORT))
    else:
        print("[FAIL] No response from server for GET request.")
        return None

    # Send ACK (ready) — triple handshake
    sock.sendto(build_ack(seq), (SERVER_HOST, SERVER_PORT))
    print(f"[ACK] Sent ready, starting download...")

    # Receive DATA packets
    os.makedirs(CLIENT_DIR, exist_ok=True)
    save_path = os.path.join(CLIENT_DIR, filename)
    received_chunks = {}
    expected_seq = seq

    while True:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                sock.settimeout(TIMEOUT)
                raw, _ = sock.recvfrom(4096 + CHUNK_SIZE)
                pkt = parse_packet(raw)

                if pkt["type"] == ERROR:
                    print(f"[ERROR] Received error_type={pkt['error_type']} during transfer")
                    return None

                if pkt["type"] == DATA:
                    seq = pkt["seq"]
                    eof = pkt["eof"]
                    payload = pkt["payload"]

                    if seq != expected_seq:
                        print(f"[UNEXPECTED] Expected seq={expected_seq}, got seq={seq}")
                        sock.sendto(build_error(ERR_UNEXPECTED), (SERVER_HOST, SERVER_PORT))
                        continue

                    print(f"[DATA] Received seq={seq} EOF={eof} size={len(payload)} bytes")
                    received_chunks[seq] = payload

                    sock.sendto(build_ack(seq), (SERVER_HOST, SERVER_PORT))
                    print(f"[ACK] Sent seq={seq}")

                    expected_seq += 1

                    if eof == EOF_LAST:
                        print(f"[EOF] Last packet received, saving file...")
                        with open(save_path, "wb") as f:
                            for k in sorted(received_chunks.keys()):
                                f.write(received_chunks[k])
                        print(f"[DONE] File saved to {save_path}")
                        return expected_seq  # return updated seq

                    break

            except socket.timeout:
                print(f"[TIMEOUT] Waiting for DATA seq={expected_seq} (attempt {attempt})")
        else:
            print(f"[FAIL] Max retries reached waiting for seq={expected_seq}")
            return None


# =======================================
#  Upload (PUT)
# =======================================

def upload(sock, filename, seq):
    """
    Send a file to the server.
    Reads from CLIENT_DIR.
    Returns updated seq on success, None on failure.
    """
    filepath = os.path.join(CLIENT_DIR, filename)

    if not os.path.exists(filepath):
        print(f"[ERROR] File '{filename}' not found in {CLIENT_DIR}")
        return None

    filesize = os.path.getsize(filepath)

    # Send REQUEST
    for attempt in range(1, MAX_RETRIES + 1):
        sock.sendto(build_request_put(filename, filesize), (SERVER_HOST, SERVER_PORT))
        print(f"[REQUEST] PUT {filename} size={filesize}")

        try:
            sock.settimeout(TIMEOUT)
            raw, _ = sock.recvfrom(4096)
            pkt = parse_packet(raw)

            if pkt["type"] == ERROR:
                print(f"[ERROR] Server denied upload: error_type={pkt['error_type']}")
                return None

            if pkt["type"] == ACK and pkt["subtype"] == "filesize":
                print(f"[ACK] Server ready, confirmed size={pkt['filesize']}")
                break

        except socket.timeout:
            print(f"[TIMEOUT] Waiting for server response (attempt {attempt})")
    else:
        print("[FAIL] No response from server for PUT request.")
        return None

    # Send ACK (ready) — triple handshake
    sock.sendto(build_ack(seq), (SERVER_HOST, SERVER_PORT))
    print(f"[ACK] Sent ready, starting upload...")

    # Read and send file in chunks
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break

            next_chunk = f.read(CHUNK_SIZE)
            eof = EOF_LAST if not next_chunk else EOF_MORE

            if next_chunk:
                f.seek(-len(next_chunk), 1)

            for attempt in range(1, MAX_RETRIES + 1):
                sock.sendto(build_data(seq, chunk, eof=eof), (SERVER_HOST, SERVER_PORT))
                print(f"[DATA] Sent seq={seq} EOF={eof} size={len(chunk)} bytes (attempt {attempt})")

                try:
                    sock.settimeout(TIMEOUT)
                    raw, _ = sock.recvfrom(4096)
                    pkt = parse_packet(raw)

                    if pkt["type"] == ACK and pkt["seq"] == seq:
                        print(f"[ACK] Received seq={seq}")
                        seq += 1
                        break

                    if pkt["type"] == ERROR:
                        print(f"[ERROR] Received error_type={pkt['error_type']} during upload")
                        return None

                except socket.timeout:
                    print(f"[TIMEOUT] No ACK for seq={seq}, retransmitting...")
            else:
                print(f"[FAIL] Max retries reached for seq={seq}")
                return None

    print(f"[DONE] Upload complete.")
    return seq  # return updated seq


# =======================================
#  Teardown
# =======================================

def teardown(sock):
    """Send FIN and wait for FIN-ACK to close session."""
    for attempt in range(1, MAX_RETRIES + 1):
        sock.sendto(build_fin(), (SERVER_HOST, SERVER_PORT))
        print(f"[FIN] Sent (attempt {attempt})")

        try:
            sock.settimeout(TIMEOUT)
            raw, _ = sock.recvfrom(4096)
            pkt = parse_packet(raw)

            if pkt["type"] == FIN_ACK:
                print(f"[FIN-ACK] Received, session closed.")
                return True

        except socket.timeout:
            print(f"[TIMEOUT] Waiting for FIN-ACK (attempt {attempt})")

    print("[FAIL] Teardown failed after max retries.")
    return False