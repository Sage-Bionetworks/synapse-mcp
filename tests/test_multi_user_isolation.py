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
    def __init__(self):
        self._state = {}

    async def get_state(self, key, default=None):
        return self._state.get(key, default)

    async def set_state(self, key, value, serializable=True):
        self._state[key] = value


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
