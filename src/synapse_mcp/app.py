"""Core MCP application setup."""

from datetime import datetime, timezone
import logging
import os

from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .oauth import create_oauth_proxy
from .auth_middleware import OAuthTokenMiddleware, PATAuthMiddleware

logger = logging.getLogger("synapse_mcp.app")
asgi_logger = logging.getLogger("synapse_mcp.asgi")


class RequestLoggingMiddleware:
    """Log ALL incoming HTTP requests at ASGI level for debugging.

    This middleware captures requests BEFORE FastMCP processes them,
    allowing us to debug authentication issues where requests fail
    before reaching our application code.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Decode headers from bytes to strings
            headers = {
                k.decode('latin1'): v.decode('latin1')
                for k, v in scope.get("headers", [])
            }

            asgi_logger.info("=== ASGI RAW REQUEST ===")
            asgi_logger.info("Method: %s", scope.get("method"))
            asgi_logger.info("Path: %s", scope.get("path"))
            asgi_logger.info("Query string: %s", scope.get("query_string", b"").decode('latin1'))
            asgi_logger.info("All headers: %s", headers)

            # Specifically check for Authorization header
            auth_header = headers.get("authorization", "MISSING")
            if auth_header != "MISSING":
                asgi_logger.info("Authorization header: %s",
                               auth_header[:50] + "..." if len(auth_header) > 50 else auth_header)
            else:
                asgi_logger.warning("Authorization header: MISSING - this will cause 401 Unauthorized")

        # Call the wrapped app
        try:
            await self.app(scope, receive, send)
        except Exception as exc:
            asgi_logger.error("=== ASGI REQUEST FAILED ===")
            asgi_logger.error("Exception: %s", exc, exc_info=True)
            raise


# Determine authentication mode and configure server accordingly
auth = create_oauth_proxy()
has_pat = bool(os.environ.get("SYNAPSE_PAT"))
has_oauth = bool(
    os.environ.get("SYNAPSE_OAUTH_CLIENT_ID")
    and os.environ.get("SYNAPSE_OAUTH_CLIENT_SECRET")
)

# Server instructions
_INSTRUCTIONS = (
    "Synapse is a collaborative data platform for researchers where data is organized in public or private projects. "
    "Synapse MCP Server helps users discover and understand Synapse data that they can see, providing tools for: "
    "searches, wiki retrieval, metadata retrieval, and project traversal (through projects/folders). "
    "Review entity metadata for attribution and licensing. "
    "Each connection must authenticate with a Synapse."
)

if auth and has_oauth:
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=[
                "mcp-protocol-version",
                "mcp-session-id",
                "Authorization",
                "Content-Type",
            ],
            expose_headers=["mcp-session-id"],
        )
    ]
    # Production mode: OAuth authentication
    mcp = FastMCP("Synapse MCP Server", instructions=_INSTRUCTIONS,
                  auth=auth, middleware=middleware)
    mcp.add_middleware(OAuthTokenMiddleware())

    # Wrap with ASGI-level request logging to debug auth issues
    # We need to monkey-patch mcp.http_app() so that when __main__.py calls mcp.run(),
    # it uses our wrapped app with request logging
    original_http_app = mcp.http_app

    def wrapped_http_app(*args, **kwargs):
        asgi_app = original_http_app(*args, **kwargs)
        return RequestLoggingMiddleware(asgi_app)

    mcp.http_app = wrapped_http_app
    app = mcp.http_app()  # Also store for direct ASGI usage

    logger.info("Server configured for OAuth authentication (production mode)")
    logger.info("ASGI request logging enabled for debugging (wrapped mcp.http_app)")
    print("🔐 OAuth authentication configured (production mode)")
    print("🔍 ASGI request logging enabled for debugging")

    # Log FastMCP's internal state for debugging
    logger.info("FastMCP auth type: %s", type(auth).__name__)
    logger.info("FastMCP mcp type: %s", type(mcp).__name__)
    logger.info("FastMCP mcp dir: %s", [
                attr for attr in dir(mcp) if not attr.startswith("_")])

    if has_pat:
        logger.warning(
            "Both SYNAPSE_PAT and OAuth credentials detected. "
            "Using OAuth (production mode). "
            "Remove SYNAPSE_OAUTH_CLIENT_ID/SECRET to use PAT mode."
        )
        print("⚠️  Warning: SYNAPSE_PAT ignored in OAuth mode")

elif has_pat:
    # Development mode: PAT authentication
    mcp = FastMCP("Synapse MCP Server", instructions=_INSTRUCTIONS, auth=None)
    mcp.add_middleware(PATAuthMiddleware())

    # Wrap with ASGI-level request logging (also useful for PAT mode debugging)
    # Monkey-patch mcp.http_app() so __main__.py uses our wrapped app
    original_http_app = mcp.http_app

    def wrapped_http_app(*args, **kwargs):
        asgi_app = original_http_app(*args, **kwargs)
        return RequestLoggingMiddleware(asgi_app)

    mcp.http_app = wrapped_http_app
    app = mcp.http_app()  # Also store for direct ASGI usage

    logger.info("Server configured for PAT authentication (development mode)")
    logger.info("ASGI request logging enabled for debugging (wrapped mcp.http_app)")
    print("🔧 PAT authentication configured (development mode)")
    print("🔍 ASGI request logging enabled for debugging")

else:
    # No authentication configured
    raise ValueError(
        "No authentication configured. Set one of:\n"
        "  Production (OAuth): SYNAPSE_OAUTH_CLIENT_ID + SYNAPSE_OAUTH_CLIENT_SECRET\n"
        "  Development (PAT):  SYNAPSE_PAT"
    )


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Standard HTTP health check endpoint for Kubernetes and monitoring systems."""
    return JSONResponse(
        {
            "status": "healthy",
            "service": "synapse-mcp",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "version": "0.2.0",
            "is_oauth_configured": bool(
                os.environ.get("SYNAPSE_OAUTH_CLIENT_ID")
                and os.environ.get("SYNAPSE_OAUTH_CLIENT_SECRET")
            ),
        }
    )


__all__ = ["auth", "mcp", "health_check", "app"]
