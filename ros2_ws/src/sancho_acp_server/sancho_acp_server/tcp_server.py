"""TCP transport adapter for the Sancho ACP server.

Since the ACP standard does not yet support HTTP natively, this module
provides a raw TCP transport layer. ACP clients connect via TCP sockets,
and each connection gets its own ``AgentSideConnection`` backed by a fresh
``SanchoAgent`` instance.

The ACP SDK operates on ``asyncio.StreamReader`` / ``asyncio.StreamWriter``
pairs, which is exactly what ``asyncio.start_server`` provides — making the
adapter straightforward.

Usage::

    python -m sancho_acp_server.tcp_server [--host HOST] [--port PORT]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Ensure the package root is on the import path so that ``sancho_acp_server``
# can be resolved when running directly with ``python -m``.
_pkg_root = Path(__file__).resolve().parent.parent
if str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

from acp.agent.connection import AgentSideConnection  # noqa: E402

from .agent import SanchoAgent  # noqa: E402

logger = logging.getLogger("sancho_acp_server.tcp_server")

# Default buffer limit for the TCP stream (50 MB — matches ACP SDK default).
TCP_BUFFER_LIMIT = 50 * 1024 * 1024


async def _handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    """Handle a single incoming ACP client connection."""
    peer = writer.get_extra_info("peername")
    logger.info("New ACP client connected from %s", peer)

    agent = SanchoAgent()

    try:
        conn = AgentSideConnection(
            agent,
            writer,       # input_stream  (server writes TO client)
            reader,       # output_stream (server reads FROM client)
            listening=False,
            use_unstable_protocol=True,
        )
        await conn.listen()
    except asyncio.CancelledError:
        logger.info("Connection cancelled for %s", peer)
    except Exception:
        logger.exception("Connection error for %s", peer)
    finally:
        logger.info("ACP client disconnected: %s", peer)
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def serve(host: str, port: int) -> None:
    """Start the TCP server and listen for ACP client connections."""
    server = await asyncio.start_server(
        _handle_client,
        host=host,
        port=port,
        limit=TCP_BUFFER_LIMIT,
    )

    addrs = ", ".join(str(s.getsockname()) for s in server.sockets)
    logger.info("Sancho ACP TCP server listening on %s", addrs)
    print(f"✅ Sancho ACP TCP server listening on {addrs}")
    print("   Waiting for ACP client connections...")

    async with server:
        await server.serve_forever()


def main() -> None:
    """Entry point: parse arguments and start the TCP server."""
    # Load .env from the package root directory.
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)

    parser = argparse.ArgumentParser(
        description="Sancho ACP Server — TCP transport"
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("SANCHO_ACP_HOST", "0.0.0.0"),
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("SANCHO_ACP_PORT", "9100")),
        help="Port to listen on (default: 9100)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG-level logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    try:
        asyncio.run(serve(args.host, args.port))
    except KeyboardInterrupt:
        print("\nSancho ACP server stopped.")


if __name__ == "__main__":
    main()
