"""Tests for _OAuthFixupMiddleware in app.py."""

import json

import pytest

from synapse_mcp.app import _OAuthFixupMiddleware


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_asgi_app(response_body: dict, status: int = 200):
    """Create a minimal ASGI app that returns a JSON response."""
    body = json.dumps(response_body).encode()

    async def app(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": body,
                "more_body": False,
            }
        )

    return app


async def _invoke_metadata(middleware, path="/.well-known/oauth-authorization-server"):
    """Send a GET request to the metadata endpoint through the middleware."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "query_string": b"",
        "headers": [],
    }

    received_status = None
    received_body = b""

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        nonlocal received_status, received_body
        if message["type"] == "http.response.start":
            received_status = message.get("status")
        elif message["type"] == "http.response.body":
            received_body += message.get("body", b"")

    await middleware(scope, receive, send)
    return received_status, json.loads(received_body)


class TestHandleMetadata:
    """Tests for _handle_metadata patching of authorization server metadata."""

    async def test_injects_scopes_supported_when_missing(self):
        """scopes_supported should be injected when not present in upstream."""
        upstream = {
            "issuer": "https://auth.example.com",
            "authorization_endpoint": "https://auth.example.com/authorize",
            "token_endpoint": "https://auth.example.com/token",
            "token_endpoint_auth_methods_supported": ["none"],
        }
        middleware = _OAuthFixupMiddleware(_make_asgi_app(upstream))

        _, data = await _invoke_metadata(middleware)

        assert data["scopes_supported"] == ["openid", "view"]

    async def test_preserves_existing_scopes_supported(self):
        """If upstream already has scopes_supported, don't overwrite it."""
        upstream = {
            "issuer": "https://auth.example.com",
            "token_endpoint_auth_methods_supported": ["none"],
            "scopes_supported": ["custom_scope"],
        }
        middleware = _OAuthFixupMiddleware(_make_asgi_app(upstream))

        _, data = await _invoke_metadata(middleware)

        assert data["scopes_supported"] == ["custom_scope"]

    async def test_adds_none_to_token_auth_methods(self):
        """Existing behavior: 'none' is added to token_endpoint_auth_methods_supported."""
        upstream = {
            "issuer": "https://auth.example.com",
            "token_endpoint_auth_methods_supported": ["client_secret_basic"],
        }
        middleware = _OAuthFixupMiddleware(_make_asgi_app(upstream))

        _, data = await _invoke_metadata(middleware)

        assert "none" in data["token_endpoint_auth_methods_supported"]
        assert "client_secret_basic" in data["token_endpoint_auth_methods_supported"]

    async def test_both_patches_applied_together(self):
        """Both scopes_supported and token auth methods are patched in one pass."""
        upstream = {
            "issuer": "https://auth.example.com",
            "token_endpoint_auth_methods_supported": ["client_secret_post"],
        }
        middleware = _OAuthFixupMiddleware(_make_asgi_app(upstream))

        _, data = await _invoke_metadata(middleware)

        assert data["scopes_supported"] == ["openid", "view"]
        assert "none" in data["token_endpoint_auth_methods_supported"]

    async def test_content_length_updated(self):
        """Content-Length header is updated after patching."""
        upstream = {
            "issuer": "https://auth.example.com",
            "token_endpoint_auth_methods_supported": ["client_secret_basic"],
        }
        middleware = _OAuthFixupMiddleware(_make_asgi_app(upstream))

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/.well-known/oauth-authorization-server",
            "query_string": b"",
            "headers": [],
        }

        headers_received = []
        body_received = b""

        async def receive():
            return {"type": "http.request", "body": b""}

        async def send(message):
            nonlocal headers_received, body_received
            if message["type"] == "http.response.start":
                headers_received = message.get("headers", [])
            elif message["type"] == "http.response.body":
                body_received += message.get("body", b"")

        await middleware(scope, receive, send)

        content_length = None
        for k, v in headers_received:
            if k == b"content-length":
                content_length = int(v)
        assert content_length == len(body_received)


class TestPathScopedMetadataAlias:
    """Tests for /.well-known/oauth-authorization-server/mcp alias."""

    async def test_mcp_path_returns_metadata(self):
        """Path-scoped URL serves the same metadata as the root."""
        upstream = {
            "issuer": "https://auth.example.com",
            "token_endpoint_auth_methods_supported": [
                "client_secret_basic",
            ],
        }
        middleware = _OAuthFixupMiddleware(_make_asgi_app(upstream))

        _, data = await _invoke_metadata(
            middleware,
            path="/.well-known/oauth-authorization-server/mcp",
        )

        assert data["issuer"] == "https://auth.example.com"
        assert data["scopes_supported"] == ["openid", "view"]
        assert "none" in data[
            "token_endpoint_auth_methods_supported"
        ]

    async def test_mcp_path_rewrites_to_root(self):
        """The /mcp path is rewritten so the downstream app sees the root."""
        captured_paths = []

        async def tracking_app(scope, receive, send):
            captured_paths.append(scope["path"])
            body = json.dumps({"issuer": "x"}).encode()
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": body,
                "more_body": False,
            })

        middleware = _OAuthFixupMiddleware(tracking_app)
        await _invoke_metadata(
            middleware,
            path="/.well-known/oauth-authorization-server/mcp",
        )

        assert captured_paths == [
            "/.well-known/oauth-authorization-server"
        ]
