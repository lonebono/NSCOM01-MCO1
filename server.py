import socket
import argparse
import random
from protocol import *

def start_server(host, port):
    # Using UDP (SOCK_DGRAM) as required [cite: 157]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    print(f"Server listening on {host}:{port}...")

    # listen for SYN
    while True:
        raw_bytes, client_addr = sock.recvfrom(CHUNK_SIZE)
        msg = parse_packet(raw_bytes)
        if msg["type"] == SYN:
            conn = establish_connection(sock, client_addr, raw_bytes)

            if conn == 0:
                print(f"Could not establish connection with {client_addr}.")
            if conn == 1:
                try:
                    sock.settimeout(TIMEOUT)
                    req_bytes, client_addr = sock.recvfrom(CHUNK_SIZE)
                    req = parse_packet(req_bytes)

                    if req["type"] == GET:
                        pass
                    if req["type"] == PUT:
                        pass
                    if req["type"] == FIN:
                        pass

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
            recv_bytes, addr = sock.recvfrom(CHUNK_SIZE)
            packet = parse_packet(recv_bytes)
            if packet["type"] == ACK:
                if expected_ack == packet["ack"]:
                    print(f"Handshake complete with {addr}")
                    return 1
                else:
                    print(f"Handshake failed with {addr}")
                    return 0

        except socket.error:
            print("Client no response, trying again.")
            continue
        finally:
            print("Handshake reached max retries.")
            sock.settimeout(None)
    return 0
