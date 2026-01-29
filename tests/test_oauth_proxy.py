"""Tests for the OAuth proxy with user-based token storage."""

import json
from types import SimpleNamespace
import sys

import pytest
from fastmcp.server.auth.oauth_proxy import OAuthClientInformationFull, OAuthProxy
from starlette.responses import RedirectResponse

import synapse_mcp.connection_auth as connection_auth
from synapse_mcp.oauth.proxy import SessionAwareOAuthProxy


pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeRegistry:
    def __init__(self):
        self.records = {}

    def load_all(self):
        return list(self.records.values())

    def save(self, registration):
        self.records[registration.client_id] = registration

    def remove(self, client_id):
        self.records.pop(client_id, None)


class FakeStorage:
    def __init__(self):
        self.tokens = {}
        self.set_calls = []
        self.removed = []

    async def get_all_user_subjects(self):
        return set(self.tokens.keys())

    async def find_user_by_token(self, token):
        for subject, stored in self.tokens.items():
            if stored == token:
                return subject
        return None

    async def set_user_token(self, user_subject, access_token, ttl_seconds=3600):
        self.tokens[user_subject] = access_token
        self.set_calls.append((user_subject, access_token))

    async def get_user_token(self, user_subject):
        return self.tokens.get(user_subject)

    async def remove_user_token(self, user_subject):
        self.tokens.pop(user_subject, None)
        self.removed.append(user_subject)

    async def cleanup_expired_tokens(self):
        return None


def build_proxy(monkeypatch, storage, registry: FakeRegistry | None = None, token_verifier=None):
    monkeypatch.setattr(
        "synapse_mcp.oauth.proxy.create_session_storage", lambda: storage)
    if registry is not None:
        monkeypatch.setattr(
            "synapse_mcp.oauth.proxy.create_client_registry", lambda *_, **__: registry)
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
async def test_map_new_tokens_populates_storage(monkeypatch):
    storage = FakeStorage()
    proxy = build_proxy(monkeypatch, storage, FakeRegistry())
    proxy._access_tokens = {"token123": object()}

    dummy_jwt = SimpleNamespace(
        decode=lambda token, options=None: {"sub": "user-1"})
    monkeypatch.setitem(sys.modules, "jwt", dummy_jwt)

    await proxy._map_new_tokens_to_users()

    assert storage.tokens["user-1"] == "token123"


@pytest.mark.anyio
async def test_get_token_for_current_user(monkeypatch):
    storage = FakeStorage()
    storage.tokens["user-1"] = "token123"
    proxy = build_proxy(monkeypatch, storage, FakeRegistry())

    result = await proxy.get_token_for_current_user()
    assert result == ("token123", "user-1")
    assert await proxy.iter_user_tokens() == [("user-1", "token123")]


@pytest.mark.anyio
async def test_cleanup_expired_tokens_removes_orphans(monkeypatch):
    storage = FakeStorage()
    storage.tokens["user-1"] = "token123"
    proxy = build_proxy(monkeypatch, storage, FakeRegistry())

    proxy._access_tokens = {"token123": object(), "token999": object()}
    monkeypatch.setattr(SessionAwareOAuthProxy,
                        "_is_token_old_enough_to_cleanup", lambda self, token: True)

    await proxy.cleanup_expired_tokens()

    assert "token999" not in proxy._access_tokens
    assert "token123" in proxy._access_tokens


@pytest.mark.anyio
async def test_handle_callback_sanitizes_none_state(monkeypatch):
    storage = FakeStorage()
    proxy = build_proxy(monkeypatch, storage, FakeRegistry())

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
    storage = FakeStorage()
    proxy = build_proxy(monkeypatch, storage, FakeRegistry())

    async def fake_handle(self, request, *args, **kwargs):
        return RedirectResponse("http://app/callback?code=token&state=valid123")

    monkeypatch.setattr(OAuthProxy, "_handle_idp_callback", fake_handle)

    request = SimpleNamespace(headers={})

    response = await proxy._handle_idp_callback(request)

    assert response.headers["location"].endswith("state=valid123")


@pytest.mark.anyio
async def test_client_registry_persists_across_instances(monkeypatch, tmp_path):
    registry_path = tmp_path / "clients.json"
    monkeypatch.setenv("SYNAPSE_MCP_CLIENT_REGISTRY_PATH", str(registry_path))

    storage = FakeStorage()
    proxy = build_proxy(monkeypatch, storage)

    client_info = OAuthClientInformationFull(
        client_id="client-xyz",
        client_secret="secret",
        redirect_uris=["http://127.0.0.1:5000/callback"],
        grant_types=["authorization_code"],
    )

    await proxy.register_client(client_info)

    saved = json.loads(registry_path.read_text())
    assert "client-xyz" in saved

    new_storage = FakeStorage()
    new_proxy = build_proxy(monkeypatch, new_storage)

    assert "client-xyz" in new_proxy._clients


@pytest.mark.anyio
async def test_static_clients_loaded_from_env(monkeypatch):
    payload = json.dumps(
        [
            {
                "client_id": "static-client",
                "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
            }
        ]
    )
    monkeypatch.setenv("SYNAPSE_MCP_STATIC_CLIENTS", payload)

    storage = FakeStorage()
    proxy = build_proxy(monkeypatch, storage, FakeRegistry())

    assert "static-client" in proxy._clients


@pytest.mark.anyio
async def test_verify_token_allows_connection_auth(monkeypatch):
    class DummyVerifier:
        required_scopes = ["view"]

        async def verify_token(self, token):
            return SimpleNamespace(
                token=token,
                raw_token=token,
                client_id="client-123",
                scopes=["view"],
                expires_at=999999999,
                sub="user-123",
            )

    storage = FakeStorage()
    proxy = build_proxy(monkeypatch, storage, FakeRegistry(),
                        token_verifier=DummyVerifier())

    token = "oauth-token-123"
    access_token = await proxy.verify_token(token)
    assert access_token is not None
    assert access_token.scopes == ["view"]

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

        def get_state(self, key, default=None):
            if key in self._state:
                return self._state[key]
            if default is not None:
                return default
            raise KeyError(key)

        def set_state(self, key, value):
            self._state[key] = value

    ctx = DummyContext()
    ctx.set_state("oauth_access_token", token)

    client = connection_auth.get_synapse_client(ctx)
    assert isinstance(client, DummySynapse)
    assert client.logged_in == token
