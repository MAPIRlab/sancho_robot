from . import mcp_app
from .bridge import SanchoBridgeNode
from .mcp_app import mcp


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
    args, _unknown = parser.parse_known_args()

    import rclpy

    rclpy.init()
    node = SanchoBridgeNode()
    mcp_app.sancho_node = node

    try:
        print(
            f"Starting Sancho FastMCP Server on {args.transport} "
            f"(Host: {args.host}, Port: {args.port})..."
        )
        if args.transport == "http":
            mcp.run(transport="http", host=args.host, port=args.port)
        else:
            mcp.run(transport="stdio")
    except KeyboardInterrupt:
        pass
    finally:
        mcp_app.sancho_node = None
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
        # 1. Navigation setup
