"""Connection-scoped authentication regression tests."""

import pytest

import synapse_mcp
import synapse_mcp.connection_auth as connection_auth
from synapse_mcp.connection_auth import ConnectionAuthError, get_user_auth_info

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"


class DummyContext:
    """Context stand-in mirroring FastMCP's request- vs session-scoped state.

    ``serializable=False`` values land in a per-instance request-scoped dict.
    ``serializable=True`` values land in a process-global store keyed by
    ``session_id`` — the same store two requests would share if they present
    the same ``mcp-session-id`` header.

    ``set_state`` takes ``serializable`` keyword-only, matching FastMCP's real
    signature, so a positional call raises instead of silently passing.
    """

    _session_store: dict = {}
    _counter = 0

    def __init__(self, session_id=None):
        if session_id is None:
            DummyContext._counter += 1
            session_id = f"req-{DummyContext._counter}"
        self.session_id = session_id
        self._request_state = {}

    def _session_key(self, key):
        return f"{self.session_id}:{key}"

    async def get_state(self, key, default=None):
        if key in self._request_state:
            return self._request_state[key]
        return self._session_store.get(self._session_key(key), default)

    async def set_state(self, key, value, *, serializable=True):
        if serializable:
            self._session_store[self._session_key(key)] = value
        else:
            self._request_state[key] = value


def _make_client(user_id: str):
    class _Client:
        def __init__(self, user):
            self._user = user

        def login(self, **kwargs):
            return None

        def getUserProfile(self):
            return {
                "ownerId": self._user,
                "userName": f"{self._user}@example.com",
            }

    return _Client(user_id)


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    monkeypatch.delenv("SYNAPSE_PAT", raising=False)
    DummyContext._session_store.clear()


async def test_get_synapse_client_creates_connection_scoped_clients(monkeypatch):
    ctx1 = DummyContext()
    ctx2 = DummyContext()

    # Simulate middleware injecting PAT token into context
    await ctx1.set_state("synapse_pat_token", "fake-pat")
    await ctx2.set_state("synapse_pat_token", "fake-pat")

    clients = [_make_client("user1"), _make_client("user2")]
    monkeypatch.setattr(connection_auth.synapseclient, "Synapse", lambda *args, **kwargs: clients.pop(0))

    client1 = await connection_auth.get_synapse_client(ctx1)
    client2 = await connection_auth.get_synapse_client(ctx2)

    assert client1 is not client2
    assert (await get_user_auth_info(ctx1))["user_id"] == "user1"
    assert (await get_user_auth_info(ctx2))["user_id"] == "user2"


async def test_get_synapse_client_uses_cached_client(monkeypatch):
    ctx = DummyContext()
    created = []

    # Simulate middleware injecting PAT token into context
    await ctx.set_state("synapse_pat_token", "fake-pat")

    def factory(*args, **kwargs):
        client = _make_client("cached")
        created.append(client)
        return client

    monkeypatch.setattr(connection_auth.synapseclient, "Synapse", factory)

    first = await connection_auth.get_synapse_client(ctx)
    second = await connection_auth.get_synapse_client(ctx)

    assert first is second
    assert len(created) == 1


async def test_get_synapse_client_requires_credentials(monkeypatch):
    ctx = DummyContext()

    monkeypatch.setattr(connection_auth.synapseclient, "Synapse", lambda *args, **kwargs: _make_client("anon"))

    with pytest.raises(ConnectionAuthError):
        await connection_auth.get_synapse_client(ctx)


async def test_given_two_connections_when_service_called_then_each_gets_own_client(
    monkeypatch,
):
    """Verify that the service layer yields connection-scoped clients."""
    ctx1 = DummyContext()
    ctx2 = DummyContext()
    await ctx1.set_state("synapse_pat_token", "fake-pat")
    await ctx2.set_state("synapse_pat_token", "fake-pat")

    client1 = _make_client("user1")
    client2 = _make_client("user2")
    clients = [client1, client2]
    monkeypatch.setattr(
        connection_auth.synapseclient,
        "Synapse",
        lambda *args, **kwargs: clients.pop(0),
    )

    from synapse_mcp.services.tool_service import synapse_client

    async with synapse_client(ctx1) as c1:
        async with synapse_client(ctx2) as c2:
            assert c1 is not c2
            assert c1._user == "user1"
            assert c2._user == "user2"


async def test_auth_state_is_request_scoped_not_session_scoped(monkeypatch):
    """Two requests sharing an mcp-session-id must not cross auth state.

    The synapseclient, user_auth_info, and auth_initialized flag are stored
    request-scoped (serializable=False), so nothing lands in the process-global
    session store that a colliding session_id could read.
    """
    ctx1 = DummyContext(session_id="shared-session")
    ctx2 = DummyContext(session_id="shared-session")

    # Token is injected request-scoped, as the middleware now does.
    await ctx1.set_state("synapse_pat_token", "fake-pat", serializable=False)
    await ctx2.set_state("synapse_pat_token", "fake-pat", serializable=False)

    clients = [_make_client("user1"), _make_client("user2")]
    monkeypatch.setattr(
        connection_auth.synapseclient,
        "Synapse",
        lambda *args, **kwargs: clients.pop(0),
    )

    client1 = await connection_auth.get_synapse_client(ctx1)
    client2 = await connection_auth.get_synapse_client(ctx2)

    assert client1 is not client2
    assert (await get_user_auth_info(ctx1))["user_id"] == "user1"
    assert (await get_user_auth_info(ctx2))["user_id"] == "user2"

    # No per-request auth state leaked into the shared session store.
    for key in (
        "synapse_client",
        "user_auth_info",
        "auth_initialized",
        "synapse_pat_token",
    ):
        assert f"shared-session:{key}" not in DummyContext._session_store


async def test_set_state_passes_serializable_by_keyword():
    """_set_state must pass serializable by keyword (FastMCP made it kw-only)."""

    class KeywordOnlyContext:
        def __init__(self):
            self.calls = []

        async def set_state(self, key, value, *, serializable=True):
            self.calls.append((key, value, serializable))

    ctx = KeywordOnlyContext()
    await connection_auth._set_state(ctx, "k", "v", serializable=False)

    assert ctx.calls == [("k", "v", False)]
