import logging
from . import mcp_app
from .bridge import SanchoBridgeNode
from .mcp_app import mcp

logger = logging.getLogger("sancho_mcp_server")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Sancho MCP Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to for HTTP server")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on for HTTP server")
    parser.add_argument(
        "--transport",
        default="http",
        choices=["stdio", "http"],
        help="Transport type",
    )
    parser.add_argument("--mock", action="store_true", help="Run in mock mode with fake data (no ROS needed)")
    args, _unknown = parser.parse_known_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    if args.mock:
        logger.info("🔧 Running Sancho MCP Server in MOCK MODE with fake data (no ROS node initialized)")
        mcp_app.mock_mode = True
    else:
        import rclpy
        rclpy.init()
        node = SanchoBridgeNode()
        mcp_app.sancho_node = node

    try:
        logger.info(
            f"Starting Sancho FastMCP Server on {args.transport} "
            f"(Host: {args.host}, Port: {args.port}, Mock: {args.mock})..."
        )
        if args.transport == "http":
            mcp.run(transport="http", host=args.host, port=args.port)
        else:
            mcp.run(transport="stdio")
    except KeyboardInterrupt:
        pass
    finally:
        if not args.mock:
            mcp_app.sancho_node = None
            if "node" in locals():
                node.destroy_node()
            rclpy.shutdown()


if __name__ == "__main__":
    main()
        # 1. Navigation setup
