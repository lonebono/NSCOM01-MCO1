import random

# =========================================
#  Message Type Constants
# =========================================
SYN         = "SYN"
SYN_ACK     = "SYN-ACK"
ACK         = "ACK"
FIN         = "FIN"
FIN_ACK     = "FIN-ACK"
DATA        = "DATA"
REQUEST     = "REQUEST"
ERROR       = "ERROR"

# =========================================
#  Operation Type Constants
# =========================================
GET         = "GET"
PUT         = "PUT"

# =========================================
#  Error Type Constants
# =========================================
ERR_TIMEOUT     = 0   # Server or client unresponsive
ERR_NOT_FOUND   = 1   # File not found
ERR_UNEXPECTED  = 2   # Unexpected/mismatched packets

# =========================================
#  EOF Constants
# =========================================
EOF_MORE    = 0   # More data to follow
EOF_LAST    = 1   # Last packet

# =========================================
#  Config
# =========================================
CHUNK_SIZE  = 512       # Max payload size in bytes
TIMEOUT     = 5         # Seconds before retransmit
MAX_RETRIES = 10        # Max retransmit attempts


# =========================================
#  Packet Builders
# =========================================
def generate_isn():
    """Generate a random Initial Sequence Number (ISN)."""
    return random.randint(0, 2**32 - 1)


def build_syn(isn):
    """Client -> Server: Initiate session with ISN."""
    return f"SYN SEQ={isn}\n".encode()


def build_syn_ack(isn, seq):
    """Server -> Client: Accept session, confirm ISN."""
    return f"SYN-ACK SEQ={isn} ACK={seq+1}\n".encode()


def build_ack(seq):
    """Generic ACK with sequence number."""
    return f"ACK ACK={seq+1}\n".encode()


def build_fin(seq):
    """Whoever finishes: initiate session termination."""
    return f"FIN SEQ={seq+1}\n".encode()


def build_fin_ack(seq):
    """Response to FIN."""
    return f"FIN-ACK ACK={seq+1}\n".encode()


def build_request_get(filename):
    """Client -> Server: Request a file download."""
    return f"REQUEST GET {filename}\n".encode()


def build_request_put(filename, filesize):
    """Client -> Server: Request a file upload."""
    return f"REQUEST PUT {filename} {filesize}\n".encode()


def build_request_ack(filesize):
    """Server -> Client: Confirm file request, send file size."""
    return f"ACK filesize={filesize} OK\n".encode()


def build_error(error_type):
    """Server -> Client: Send error message."""
    return f"ERROR {error_type}\n".encode()

def build_data(seq, payload_bytes, eof=EOF_MORE):
    """
    Build a DATA packet.
    Header is text, payload is raw bytes (binary-safe).
    Format: DATA SEQ=<seq> EOF=<eof>\n<payload bytes>
    """
    header = f"DATA SEQ={seq} EOF={eof}\n".encode()
    return header + payload_bytes

# =========================================
#  Packet Parser
# =========================================

def parse_packet(raw_bytes):
    """
    Parse a raw packet back into its components.
    Returns a dict with 'type' and relevant fields.
    Raises ValueError if packet is malformed.
    """
    # Split header and payload on first newline
    # (DATA packets have binary payload after the newline)
    newline_idx = raw_bytes.index(b"\n")
    header = raw_bytes[:newline_idx].decode()
    payload = raw_bytes[newline_idx + 1:]  # binary payload (empty for non-DATA)

    parts = header.split()

    if not parts:
        raise ValueError("Empty packet")

    msg_type = parts[0]

    # SYN
    if msg_type == SYN:
        # "SYN SEQ=x"
        seq = int(parts[1].split("=")[1])
        return {"type": SYN, "seq": seq}

    # SYN-ACK
    elif msg_type == SYN_ACK:
        # "SYN-ACK SEQ=y ACK=x+1"
        seq = int(parts[1].split("=")[1])
        ack = int(parts[2].split("=")[1])
        return {"type": SYN_ACK, "seq": seq, "ack": ack}

    # ACK
    elif msg_type == ACK:
        # "ACK ACK=x" or "ACK filesize=x OK"
        if "filesize" in parts[1]:
            filesize = int(parts[1].split("=")[1])
            return {"type": ACK, "subtype": "filesize", "filesize": filesize}
        else:
            ack = int(parts[1].split("=")[1])
            return {"type": ACK, "subtype": "ack", "ack": ack}

    # FIN
    elif msg_type == FIN:
        return {"type": FIN}

    # FIN-ACK
    elif msg_type == FIN_ACK:
        return {"type": FIN_ACK}

    # REQUEST
    elif msg_type == REQUEST:
        # "REQUEST GET filename" or "REQUEST PUT filename filesize"
        operation = parts[1]
        filename = parts[2]
        if operation == GET:
            return {"type": REQUEST, "operation": GET, "filename": filename}
        elif operation == PUT:
            filesize = int(parts[3])
            return {"type": REQUEST, "operation": PUT, "filename": filename, "filesize": filesize}

    # ERROR
    elif msg_type == ERROR:
        # "ERROR 0/1/2"
        error_type = int(parts[1])
        return {"type": ERROR, "error_type": error_type}

    # DATA
    elif msg_type == DATA:
        # "DATA SEQ=x EOF=y"
        seq = int(parts[1].split("=")[1])
        eof = int(parts[2].split("=")[1])
        return {"type": DATA, "seq": seq, "eof": eof, "payload": payload}

    else:
        raise ValueError(f"Unknown packet type: {msg_type}")