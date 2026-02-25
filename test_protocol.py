from protocol import *

raw = build_syn(12345)
parsed = parse_packet(raw)
print(parsed)

raw = build_data(12345, b"hello world", eof=EOF_MORE)
parsed = parse_packet(raw)
print(parsed)

raw = build_error(ERR_NOT_FOUND)
parsed = parse_packet(raw)
print(parsed)

raw = build_request_get("photo.png")
parsed = parse_packet(raw)
print(parsed)