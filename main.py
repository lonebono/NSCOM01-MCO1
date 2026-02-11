import socket
import argparse
from protocol import RDTProtocol

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

def start_client(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"Client connecting to {host}:{port}...")

    # Skeleton for Session Establishment (SYN) [cite: 165, 166]
    syn_packet = RDTProtocol.create_packet(RDTProtocol.SYN, 0, b"Hello Server")
    sock.sendto(syn_packet, (host, port))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reliable UDP File Transfer [cite: 131]")
    parser.add_argument("role", choices=["client", "server"], help="Run as client or server")
    parser.add_argument("--host", default="127.0.0.1", help="Target host IP")
    parser.add_argument("--port", type=int, default=8080, help="Target port")

    args = parser.parse_args()

    if args.role == "server":
        start_server(args.host, args.port)
    else:
        start_client(args.host, args.port)