import socket
from client import handshake, download, upload, teardown
from client import SERVER_HOST, SERVER_PORT

def main():
    print("=" * 20)
    print("   Reliable UDP File Transfer Client")
    print("=" * 20)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"Connecting to server at {SERVER_HOST}:{SERVER_PORT}...")

    # Step 1: THREE WAY HANDSHAKE
    seq = handshake(sock)
    if seq is None:
        print("Could not establish session. Exiting.")
        sock.close()
        return

    print("\nSession established! You can now transfer files.")
    print("Commands: GET <filename> | PUT <filename> | EXIT")
    print("-" * 40)

    # Step 2: LOOP
    while True:
        try:
            command = input("\n> ").strip()
        except KeyboardInterrupt:
            print("\nInterrupted.")
            break

        if not command:
            continue

        parts = command.split()
        op = parts[0].upper()

        if op == "GET" and len(parts) == 2:
            result = download(sock, parts[1], seq)
            if result is not None:
                seq = result  # update seq for next operation

        elif op == "PUT" and len(parts) == 2:
            result = upload(sock, parts[1], seq)
            if result is not None:
                seq = result  # update seq for next operation

        elif op == "EXIT":
            break

        else:
            print("Invalid command. Use: GET <filename>, PUT <filename>, or EXIT")

    # Step 3: CLOSE
    print("\nClosing session...")
    teardown(sock)
    sock.close()
    print("Goodbye!")

if __name__ == "__main__":
    main()