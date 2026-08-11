"""Tests for connection_auth module.

Tests that connection_auth correctly reads OAuth tokens from context
that were set by the auth_middleware.
"""

import pytest

import synapse_mcp.connection_auth as connection_auth

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _clear_session_store():
    DummyContext._session_store.clear()


class DummyContext:
    """Context stand-in mirroring FastMCP's request- vs session-scoped state.

    ``serializable=False`` values land in a per-instance request-scoped dict;
    ``serializable=True`` values land in a ``session_id``-keyed store. ``set_state``
    takes ``serializable`` keyword-only, matching FastMCP's real signature, so a
    positional call raises instead of silently passing.
    """

    _session_store: dict = {}

    def __init__(self, oauth_token=None, session_id="session-1"):
        self.session_id = session_id
        self._request_state = {}
        # Middleware would have set the oauth_access_token in context. It does
        # so request-scoped (serializable=False), same as production.
        if oauth_token:
            self._request_state["oauth_access_token"] = oauth_token

    def _session_key(self, key):
        return f"{self.session_id}:{key}"

    async def get_state(self, key):
        if key in self._request_state:
            return self._request_state[key]
        session_key = self._session_key(key)
        if session_key in self._session_store:
            return self._session_store[session_key]
        raise KeyError

    async def set_state(self, key, value, *, serializable=True):
        if serializable:
            self._session_store[self._session_key(key)] = value
        else:
            self._request_state[key] = value


@pytest.fixture
def patched_synapse(monkeypatch):
    created = []

    class DummySynapse:
        def __init__(self, *args, **kwargs):
            self.init_args = args
            self.init_kwargs = kwargs
            self.logged_in = None
            created.append(self)

        def login(self, authToken=None, **kwargs):
            self.logged_in = authToken

        def getUserProfile(self):
            return {"ownerId": "user-123", "userName": "tester"}

    monkeypatch.setattr(connection_auth.synapseclient, "Synapse", DummySynapse)
    return created


@pytest.mark.anyio
async def test_oauth_authentication_uses_token_from_context(patched_synapse):
    """Test that connection_auth reads OAuth token from context (set by middleware)."""
    # Middleware has already set the token in context
    ctx = DummyContext(oauth_token="token-abc")

    client = await connection_auth.get_synapse_client(ctx)
    assert patched_synapse[0].logged_in == "token-abc"
    assert await connection_auth._get_state(ctx, connection_auth.SYNAPSE_CLIENT_KEY) is client
    assert await connection_auth._get_state(ctx, "oauth_access_token") == "token-abc"

    # The client is cached request-scoped, never in the shared session store.
    assert ctx._request_state[connection_auth.SYNAPSE_CLIENT_KEY] is client
    assert ctx._session_key(connection_auth.SYNAPSE_CLIENT_KEY) not in DummyContext._session_store
