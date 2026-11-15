"""Egress capture for scripts/testing/egress-journey.cjs (V1-A03). Linux only, needs NET_RAW.

Run in the Docker host's network namespace. Prints one JSON line per packet of interest, and only
for packets on the stack's own bridge that leave the stack's subnet:
- IPv4: a TCP SYN ("connect"), a TLS record's first bytes ("tls", for the server name) or any UDP,
  DNS included ("udp"): Docker's resolver never puts a container's lookup on the bridge;
- IPv6 to a global address ("ipv6"), whatever it carries.
Nothing is recorded from any other interface: with host networking on native Linux that traffic is
every host process's, not the stack's. No other payload is read or stored.
Usage: python -I egress-sniff.py <bridge iface> <subnet CIDR>
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
    if iface != bridge:
        return None  # off the bridge it is not the stack's traffic (see the module docstring)
    if frame[12:14] == b"\x86\xdd" or (frame[:1] and frame[0] >> 4 == 6):
        ip6 = frame[14:] if frame[12:14] == b"\x86\xdd" else frame
        if len(ip6) < 40:
            return None
        dst = ipaddress.ip_address(ip6[24:40])
        if not dst.is_global or dst.is_multicast:
            return None  # link-local neighbour discovery and multicast stay on the bridge
        return {"kind": "ipv6", "src": str(ipaddress.ip_address(ip6[8:24])), "dst": str(dst),
                "next_header": ip6[6]}
    if frame[12:14] == b"\x08\x00":
        ip = frame[14:]
    elif frame[:1] and frame[0] >> 4 == 4:
        ip = frame  # interfaces without a link header deliver bare IPv4
    else:
        return None
    ihl, proto = (ip[0] & 0x0F) * 4, ip[9]
    if proto not in (6, 17) or len(ip) < ihl + 14:
        return None
    src, dst = ipaddress.ip_address(ip[12:16]), ipaddress.ip_address(ip[16:20])
    if src not in subnet or dst in subnet:
        return None
    sport, dport = struct.unpack("!HH", ip[ihl:ihl + 4])
    event = {"src": str(src), "dst": str(dst), "sport": sport, "dport": dport}
    if proto == 17:
        return {**event, "kind": "udp"}
    flags, payload = ip[ihl + 13], ip[ihl + (ip[ihl + 12] >> 4) * 4:]
    if flags & 0x02 and not flags & 0x10:
        return {**event, "kind": "connect"}
    if payload[:1] == b"\x16":  # TLS handshake: the ClientHello carries the server name
        return {**event, "kind": "tls", "tls": payload[:2048].hex()}
    return None

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
