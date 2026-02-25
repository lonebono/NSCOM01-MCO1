import socket
import argparse
import random
from protocol import *

# DEBUGGING
# we need to handle if server timeouts, client has to close connection on their end

# =======================================
#  Config
# =======================================
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8080
SERVER_DIR  = "server/"   # folder of client files to upload/download

def start_server():
    # Using UDP (SOCK_DGRAM) as required [cite: 157]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((SERVER_HOST, SERVER_PORT))
    print(f"Server listening on {SERVER_HOST}:{SERVER_PORT}...")
    conn = 0

    # listen for SYN
    while True:
        raw_bytes, client_addr = sock.recvfrom(4096 + CHUNK_SIZE)
        init = parse_packet(raw_bytes)
        if init["type"] == SYN and conn == 0:
            conn = establish_connection(sock, client_addr, raw_bytes)

            if conn == 0:
                print(f"Could not establish connection with {client_addr}.")
            if conn == 1:
                try:
                    req_bytes, client_addr = sock.recvfrom(4096 + CHUNK_SIZE)
                    req = parse_packet(req_bytes)
                    sock.settimeout(60) # USES SEPERATE TIMEOUT TIME FOR USER CHOOSING

                    if req["type"] == REQUEST and req["operation"] == GET:
                        # get filesize of name
                        filesize = 0
                        sock.sendto(build_request_ack(filesize),client_addr)

                        req_bytes2, _ = sock.recvfrom(4096 + CHUNK_SIZE)
                        req2 = parse_packet(req_bytes2)

                        if req2["ack"] != init["seq"] + 1:
                            sock.sendto(build_error(ERR_UNEXPECTED), client_addr)

                        if req2["ack"] == init["seq"] + 1:
                            # send file packet by packet until EOF
                            pass

                    if req["type"] == REQUEST and req["operation"] == PUT:
                        pass

                    if req["type"] == FIN:
                        print(f"Initiating teardown.")
                        sock.sendto(build_fin_ack(req["seq"]), client_addr)
                        print(f"Connection ended.")

                except socket.timeout:
                    print(f"Client {client_addr} went silent after handshake.")
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
            recv_bytes, addr = sock.recvfrom(4096 + CHUNK_SIZE)
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