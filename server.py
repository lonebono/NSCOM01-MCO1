import socket
import argparse
import random
from protocol import *

def start_server(host, port):
    # Using UDP (SOCK_DGRAM) as required [cite: 157]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    print(f"Server listening on {host}:{port}...")

    while True:
        raw_bytes, client_addr = sock.recvfrom(CHUNK_SIZE)
        conn = establish_connection(sock, client_addr, raw_bytes)
        if conn == -1:
            print(f"Could not establish connection with {client_addr}.")
            return
        if conn == 1:
            while True:
                # do commands
                pass


# implementation of 3 way handshake from tcp
# returns 1 if successful, returns -1 if not
def establish_connection(sock, client_addr, raw_bytes):
    msg = parse_packet(raw_bytes)
    server_isn = generate_isn()
    expected_ack = server_isn + 1
    try:
        syn_ack = build_syn_ack(server_isn, msg["seq"])
        sock.sendto(syn_ack, client_addr)
        sock.settimeout(TIMEOUT)
        while True:
            recv_bytes, addr = sock.recvfrom(CHUNK_SIZE)
            packet = parse_packet(recv_bytes)
            if packet["type"] == "ACK":
                if expected_ack == packet["ack"]:
                    print(f"Handshake complete with {addr}")
                    return 1
                else:
                    print(f"Handshake failed with {addr}")
                    return -1

    except socket.error:
        print("Handshake timed out.")
    finally:
        sock.settimeout(None)
