import socket
import argparse
import random

def start_server(host, port):
    # Using UDP (SOCK_DGRAM) as required [cite: 157]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    print(f"Server listening on {host}:{port}...")

    while True:
        data, addr = sock.recvfrom(4096)
        msg_type, seq, payload = RDTProtocol.parse_packet(data)
        
        print(f"Received Packet: Type={msg_type}, Seq={seq}, Payload={payload.decode(errors='ignore')}")
        
        # Skeleton for ACK logic [cite: 171]
        ack_packet = RDTProtocol.create_packet(RDTProtocol.ACK, seq)
        sock.sendto(ack_packet, addr)

def send_ACK():
    pass

def recv_ACK():
    pass

# implementation of 3 way handshake from tcp
def establish_connection(sock, client_ip, message):
    # parse message from client "SYN ISN"
    parts = message.split()
    client_isn = parts[1]

    # random 32 bit integer for server ISN
    server_isn = random.randint(0, 2**32 - 1)

    send_ack = client_isn + 1

    synack_response = "SYN-ACK "+ server_isn + " " + send_ack
    sock.sendto(synack_response, client_ip)

    expected_ack = client_isn + 1
    
    sock.settimeout(20)
    try:
        while True:
            # byte buffer
            data, addr = sock.recvfrom(1024)
            # data syntax: "SYN seq ack"       
            recv_parts = data.split()
            recv_seq = int(recv_parts[1])
            recv_ack = int(recv_parts[2])

            if addr != client_ip:
                # send_error(client_ip, 2, error_desc) # type 2 unexpected packets error
                return -1, -1
            
            if recv_parts[0] != "ACK":
                # send_error(client_ip, 2, error_desc) # type 2 unexpected packets error
                return -1, -1
            
            if recv_ack != expected_ack:
                # send_error(client_ip, 2, error_desc) # type 2 unexpected packets error
                return -1, -1

            if parts[0] == "ACK" and recv_ack == expected_ack:
                print(f"Handshake complete with {client_ip}")
                return server_isn, client_isn
            
    except socket.error:
        print("Client ACK timed out, handshake failed.")
        return -1, -1

    finally:
        sock.settimeout(None)
