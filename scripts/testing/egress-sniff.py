"""Egress capture for scripts/testing/egress-journey.cjs (V1-A03). Linux only, needs NET_RAW.

Run in the Docker host's network namespace. Prints one JSON line per packet of interest:
- on the stack's bridge, each outbound packet from the stack's subnet to an outside address:
  a TCP SYN ("connect"), a TLS record's first bytes ("tls", for the server name) or any UDP,
  DNS included ("udp");
- on any other path, DNS over UDP ("dns", with its payload). Docker Desktop's resolver forwards
  lookups from the VM itself, so these name addresses but are not attributed to the stack.
No other payload is read or stored. Usage: python -I egress-sniff.py <bridge iface> <subnet CIDR>
"""

import ipaddress
import json
import socket
import struct
import sys
import time


def main(bridge: str, cidr: str) -> None:
    subnet = ipaddress.ip_network(cidr)
    sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0003))  # ETH_P_ALL
    print(json.dumps({"t": time.time(), "kind": "start", "iface": bridge, "subnet": cidr}),
          flush=True)
    while True:
        frame, (iface, *_) = sock.recvfrom(65535)
        event = packet_event(frame, iface, bridge, subnet)
        if event:
            print(json.dumps({"t": time.time(), **event}), flush=True)


def packet_event(frame: bytes, iface: str, bridge: str, subnet) -> dict | None:
    if frame[12:14] == b"\x08\x00":
        ip = frame[14:]
    elif frame[:1] and frame[0] >> 4 == 4:
        ip = frame  # interfaces without a link header deliver bare IPv4
    else:
        return None  # not IPv4 (the stack's bridge has no IPv6 by default)
    ihl, proto = (ip[0] & 0x0F) * 4, ip[9]
    if proto not in (6, 17) or len(ip) < ihl + 14:
        return None
    src, dst = ipaddress.ip_address(ip[12:16]), ipaddress.ip_address(ip[16:20])
    sport, dport = struct.unpack("!HH", ip[ihl:ihl + 4])
    event = {"src": str(src), "dst": str(dst), "sport": sport, "dport": dport}
    if iface == bridge and src in subnet and dst not in subnet:
        # Checked before DNS: Docker's resolver never puts a container's lookup on the bridge,
        # so UDP to port 53 here is a direct query to an outside server and is flagged as UDP.
        if proto == 17:
            return {**event, "kind": "udp"}
        flags, payload = ip[ihl + 13], ip[ihl + (ip[ihl + 12] >> 4) * 4:]
        if flags & 0x02 and not flags & 0x10:
            return {**event, "kind": "connect"}
        if payload[:1] == b"\x16":  # TLS handshake: the ClientHello carries the server name
            return {**event, "kind": "tls", "tls": payload[:2048].hex()}
        return None
    if proto == 17 and 53 in (sport, dport):
        return {**event, "kind": "dns", "dns": ip[ihl + 8:].hex()}
    return None

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
