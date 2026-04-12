"""Tests for the OAuth proxy behavior."""

from types import SimpleNamespace

import pytest
from fastmcp.server.auth import OAuthProxy
from starlette.responses import RedirectResponse

import synapse_mcp.connection_auth as connection_auth
from synapse_mcp.oauth.proxy import SessionAwareOAuthProxy


pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"


def build_proxy(token_verifier=None):
    if token_verifier is None:
        token_verifier = SimpleNamespace(required_scopes=[])
    return SessionAwareOAuthProxy(
        upstream_authorization_endpoint="https://auth",
        upstream_token_endpoint="https://token",
        upstream_client_id="client",
        upstream_client_secret="secret",
        redirect_path="/oauth/callback",
        token_verifier=token_verifier,
        base_url="http://localhost",
    )


@pytest.mark.anyio
async def test_handle_callback_sanitizes_none_state(monkeypatch):
    proxy = build_proxy()

    async def fake_handle(self, request, *args, **kwargs):
        return RedirectResponse("http://app/callback?code=new-token&state=None")

    monkeypatch.setattr(OAuthProxy, "_handle_idp_callback", fake_handle)

    request = SimpleNamespace(headers={})

    response = await proxy._handle_idp_callback(request)

    assert isinstance(response, RedirectResponse)
    location = response.headers["location"]
    assert "code=new-token" in location
    assert "state=None" not in location
    assert "state=" not in location


@pytest.mark.anyio
async def test_handle_callback_preserves_valid_state(monkeypatch):
    proxy = build_proxy()

    async def fake_handle(self, request, *args, **kwargs):
        return RedirectResponse("http://app/callback?code=token&state=valid123")

    monkeypatch.setattr(OAuthProxy, "_handle_idp_callback", fake_handle)

    request = SimpleNamespace(headers={})

    response = await proxy._handle_idp_callback(request)

    assert response.headers["location"].endswith("state=valid123")


@pytest.mark.anyio
async def test_static_clients_loaded_from_env(monkeypatch):
    import json

    payload = json.dumps(
        [
            {
                "client_id": "static-client",
                "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
            }
        ]
    )
    monkeypatch.setenv("SYNAPSE_MCP_STATIC_CLIENTS", payload)

    proxy = build_proxy()

    assert await proxy.get_client("static-client") is not None


@pytest.mark.anyio
async def test_connection_auth_with_oauth_token(monkeypatch):
    """Test that connection_auth.get_synapse_client works when an OAuth
    access token has been placed into the context by middleware.

    In fastmcp >=2.14.6 the OAuthProxy.verify_token() path requires tokens
    that were minted by the proxy's own JWT issuer (via the full
    exchange_authorization_code flow).  We therefore test the
    connection_auth layer independently — the middleware is responsible for
    placing the token in context, and connection_auth simply consumes it.
    """

    class DummySynapse:
        def __init__(self, *_, **__):
            self.logged_in = None

        def login(self, authToken=None, **kwargs):
            self.logged_in = authToken

        def getUserProfile(self):
            return {"ownerId": "user-123", "userName": "tester"}

    monkeypatch.setattr(connection_auth.synapseclient, "Synapse", DummySynapse)

    class DummyContext:
        def __init__(self):
            self._state = {}

        async def get_state(self, key, default=None):
            if key in self._state:
                return self._state[key]
            if default is not None:
                return default
            raise KeyError(key)

        async def set_state(self, key, value, serializable=True):
            self._state[key] = value

    token = "oauth-token-123"
    ctx = DummyContext()
    await ctx.set_state("oauth_access_token", token)

    client = await connection_auth.get_synapse_client(ctx)
    assert isinstance(client, DummySynapse)
    assert client.logged_in == token
