"""Byte forwarder: bridge.py LISTEN TARGET, each tcp:HOST:PORT or unix:PATH.

Lets an API/worker inside a no-egress network namespace reach PostgreSQL (unix -> tcp),
and lets the host reach an API listening on a unix socket inside one (tcp -> unix)."""
import asyncio
import os
import sys


def parse(spec):
    kind, _, rest = spec.partition(":")
    if kind == "tcp":
        host, _, port = rest.rpartition(":")
        return kind, (host, int(port))
    return kind, rest


async def pipe(reader, writer):
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        writer.close()


async def main():
    (lkind, laddr), (tkind, taddr) = parse(sys.argv[1]), parse(sys.argv[2])

    async def handle(r1, w1):
        try:
            r2, w2 = await (asyncio.open_connection(*taddr) if tkind == "tcp"
                            else asyncio.open_unix_connection(taddr))
        except OSError:
            w1.close()
            return
        await asyncio.gather(pipe(r1, w2), pipe(r2, w1))

    if lkind == "tcp":
        server = await asyncio.start_server(handle, *laddr)
    else:
        if os.path.exists(laddr):
            os.unlink(laddr)
        server = await asyncio.start_unix_server(handle, laddr)
    async with server:
        await server.serve_forever()


asyncio.run(main())
