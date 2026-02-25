import socket
import argparse
import time
import random
import os
from protocol import *

# DEBUGGING
# we need to handle if server timeouts, client has to close connection on their end
# added longer timeout to choose operation #

# =======================================
#  Config
# =======================================
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8080
SERVER_DIR  = "server/"   # folder of client files to upload/download

def start_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((SERVER_HOST, SERVER_PORT))
    print(f"Server listening on {SERVER_HOST}:{SERVER_PORT}...")
    conn = 0

    # listen for SYN
    while True:
        raw_bytes, client_addr = sock.recvfrom(HEADER_SIZE + CHUNK_SIZE)
        init = parse_packet(raw_bytes)
        if init["type"] == SYN and conn == 0:
            conn = establish_connection(sock, client_addr, raw_bytes)

            if conn == 0:
                print(f"Could not establish connection with {client_addr}.")
            if conn == 1:
                while True:
                    try:
                        req_bytes, client_addr = sock.recvfrom(HEADER_SIZE + CHUNK_SIZE)
                        req = parse_packet(req_bytes)
                        sock.settimeout(60) # USES SEPERATE TIMEOUT TIME FOR USER CHOOSING

                        # =======================================
                        # server side handling of GET request
                        # =======================================
                        if req["type"] == REQUEST and req["operation"] == GET:
                            filename = req["filename"]
                            filepath = os.path.join(SERVER_DIR, filename)

                            # check if file exists, if not send error
                            if not os.path.exists(filepath):
                                print(f"[ERROR] File '{filename}' not found.")
                                sock.sendto(build_error(ERR_NOT_FOUND), client_addr)
                                continue

                            filesize = os.path.getsize(filepath)
                            print(f"[REQUEST] GET {filename} size={filesize}")

                            # Send ACK (filesize, OK)
                            sock.sendto(build_request_ack(filesize), client_addr)
                            print(f"[ACK] Sent filesize={filesize}")

                            ready_ack_raw, _ = sock.recvfrom(HEADER_SIZE + CHUNK_SIZE)
                            ready_ack = parse_packet(ready_ack_raw)
                            if ready_ack["type"] != ACK:
                                sock.sendto(build_error(ERR_UNEXPECTED), client_addr)
                                continue
                            print(f"[ACK] Client ready, starting transfer...")

                            # send file by chunk
                            seq = ready_ack["ack"] - 1 # current seq of client so need to minus 1
                            done = False 
                            with open(filepath, "rb") as f:
                                while not done:
                                    chunk = f.read(CHUNK_SIZE)
                                    if not chunk:
                                        break

                                    next_chunk = f.read(CHUNK_SIZE)
                                    eof = EOF_LAST if not next_chunk else EOF_MORE
                                    if next_chunk:
                                        f.seek(-len(next_chunk), 1)

                                    for attempt in range(1, MAX_RETRIES + 1):
                                        sock.sendto(build_data(seq, chunk, eof=eof), client_addr)
                                        print(f"[DATA] Sent seq={seq} EOF={eof} size={len(chunk)} bytes (attempt {attempt})")

                                        try:
                                            sock.settimeout(TIMEOUT)
                                            ack_raw, _ = sock.recvfrom(HEADER_SIZE + CHUNK_SIZE)
                                            ack_pkt = parse_packet(ack_raw)

                                            if ack_pkt["type"] == ACK and ack_pkt["ack"] == seq + 1:
                                                print(f"[ACK] Received seq={seq}")
                                                seq += 1
                                                if eof == EOF_LAST:                       
                                                    print(f"[EOF] Last packet ACKed.")   
                                                    done = True                          
                                                break

                                            if ack_pkt["type"] == ERROR:
                                                print(f"[ERROR] Client error type={ack_pkt['error_type']}")
                                                done = True
                                                break

                                        except socket.timeout:
                                            print(f"[TIMEOUT] No ACK for seq={seq}, retransmitting... (attempt {attempt})")
                                    else:
                                        print(f"[FAIL] Max retries reached for seq={seq}")
                                        done = True

                            print(f"[DONE] File transfer complete.")

                        # =======================================
                        # server side handling of PUT request
                        # =======================================
                        if req["type"] == REQUEST and req["operation"] == PUT:
                            filename = req["filename"]
                            filesize = req["filesize"]
                            print(f"[REQUEST] PUT {filename} size={filesize}")

                            os.makedirs(SERVER_DIR, exist_ok=True)

                            # Send ACK (filesize, OK)
                            sock.sendto(build_request_ack(filesize), client_addr)
                            print(f"[ACK] Sent filesize={filesize}, ready to receive")

                            # Wait for ready ACK — triple handshake
                            ready_ack_raw, _ = sock.recvfrom(4096 + CHUNK_SIZE)
                            ready_ack = parse_packet(ready_ack_raw)
                            if ready_ack["type"] != ACK:
                                sock.sendto(build_error(ERR_UNEXPECTED), client_addr)
                                continue
                            print(f"[ACK] Client ready, starting upload receive...")

                            # Receive file chunk by chunk
                            seq = ready_ack["ack"] - 1 # current seq of client so need to minus 1
                            save_path = os.path.join(SERVER_DIR, filename)
                            received_chunks = {}
                            done = False

                            while not done:
                                for attempt in range(1, MAX_RETRIES + 1):
                                    try:
                                        sock.settimeout(TIMEOUT)
                                        data_raw, _ = sock.recvfrom(4096 + CHUNK_SIZE)
                                        data_pkt = parse_packet(data_raw)

                                        if data_pkt["type"] == ERROR:
                                            print(f"[ERROR] Client error type={data_pkt['error_type']}")
                                            done = True
                                            break

                                        if data_pkt["type"] == DATA:
                                            if data_pkt["seq"] != seq:
                                                print(f"[UNEXPECTED] Expected seq={seq}, got seq={data_pkt['seq']}")
                                                sock.sendto(build_error(ERR_UNEXPECTED), client_addr)
                                                continue

                                            print(f"[DATA] Received seq={data_pkt['seq']} EOF={data_pkt['eof']} size={len(data_pkt['payload'])} bytes")
                                            received_chunks[data_pkt["seq"]] = data_pkt["payload"]

                                            sock.sendto(build_ack(seq), client_addr)
                                            print(f"[ACK] Sent seq={seq}")
                                            seq += 1

                                            if data_pkt["eof"] == EOF_LAST:
                                                print(f"[EOF] Last packet received, saving file...")
                                                with open(save_path, "wb") as f:
                                                    for k in sorted(received_chunks.keys()):
                                                        f.write(received_chunks[k])
                                                print(f"[DONE] File saved to {save_path}")
                                                done = True
                                            break

                                    except socket.timeout:
                                        print(f"[TIMEOUT] Waiting for DATA seq={seq} (attempt {attempt})")
                                else:
                                    print(f"[FAIL] Max retries reached waiting for seq={seq}")
                                    done = True

                        # =======================================
                        # server side handling of FIN
                        # =======================================
                        if req["type"] == FIN:
                            print(f"Initiating teardown.")
                            sock.sendto(build_fin_ack(req["seq"]), client_addr)
                            print(f"[FIN-ACK] Sent, connection ended.")
                            time.sleep(0.5)
                            conn = 0
                            break

                    except socket.timeout:
                        print(f"Client {client_addr} went silent after handshake.")
                        conn = 0
                        break
                    finally:
                        sock.settimeout(None)


# implementation of 3 way handshake from tcp
# returns 1 if successful, returns 0 if not
def establish_connection(sock, client_addr, raw_bytes):
    msg = parse_packet(raw_bytes)
    server_isn = generate_isn()
    expected_ack = server_isn + 1   

    for attempt in range(1, MAX_RETRIES + 1):
        syn_ack = build_syn_ack(server_isn, msg["seq"])
        sock.sendto(syn_ack, client_addr)
        print(f"[SYN-ACK] Sent SEQ={server_isn} (attempt {attempt})")
        try:
            sock.settimeout(TIMEOUT)
            recv_bytes, addr = sock.recvfrom(HEADER_SIZE + CHUNK_SIZE)
            packet = parse_packet(recv_bytes)
            if packet["type"] == ACK:
                if expected_ack == packet["ack"]:
                    print(f"Handshake complete with {addr}")
                    return 1
                else:
                    print(f"Handshake failed with {addr}")
                    return 0

        except socket.timeout:
            print("Client no response, trying again.")
            continue
        finally:
            sock.settimeout(None)
    print("Handshake reached max retries.")
    return 0



if __name__ == "__main__":
   start_server()