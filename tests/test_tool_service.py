"""Tests for synapse_client context manager, @error_boundary decorator,
and dataclass_to_dict utility."""

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.tool_service import (
    dataclass_to_dict,
    error_boundary,
    synapse_client,
)

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"


# -------------------------------------------------------------------
# synapse_client context manager
# -------------------------------------------------------------------


@patch("synapse_mcp.services.tool_service.get_synapse_client", new_callable=AsyncMock)
class TestSynapseClient:
    async def test_given_valid_ctx_when_entering_context_then_yields_authenticated_client(
        self, mock_get_client
    ):
        # GIVEN a request context that resolves to a valid Synapse client
        expected_client = MagicMock()
        mock_get_client.return_value = expected_client
        ctx = MagicMock()

        # WHEN we enter the synapse_client context
        async with synapse_client(ctx) as client:
            # THEN it yields the authenticated client
            assert client is expected_client
        mock_get_client.assert_called_once_with(ctx)

    async def test_given_expired_credentials_when_entering_context_then_raises_auth_error(
        self, mock_get_client
    ):
        # GIVEN a request context with expired credentials
        mock_get_client.side_effect = ConnectionAuthError("expired")
        ctx = MagicMock()

        # WHEN we enter the synapse_client context
        # THEN it raises ConnectionAuthError
        with pytest.raises(ConnectionAuthError):
            async with synapse_client(ctx):
                pass


# -------------------------------------------------------------------
# @error_boundary decorator
# -------------------------------------------------------------------


class TestErrorBoundary:
    async def test_given_successful_method_when_called_then_returns_result_unchanged(self):
        # GIVEN a service method that succeeds
        class Svc:
            @error_boundary()
            async def do_thing(self, ctx):
                return {"data": 42}

        # WHEN the method is called
        result = await Svc().do_thing(MagicMock())

        # THEN the original return value passes through
        assert result == {"data": 42}

    async def test_given_auth_error_when_called_then_returns_error_dict(self):
        # GIVEN a service method that raises ConnectionAuthError
        class Svc:
            @error_boundary()
            async def do_thing(self, ctx):
                raise ConnectionAuthError("expired")

        # WHEN the method is called
        result = await Svc().do_thing(MagicMock())

        # THEN it returns an error dict with "Authentication required" message
        assert "Authentication required" in result["error"]

    async def test_given_generic_exception_when_called_then_returns_error_with_type(self):
        # GIVEN a service method that raises a ValueError
        class Svc:
            @error_boundary()
            async def do_thing(self, ctx):
                raise ValueError("bad input")

        # WHEN the method is called
        result = await Svc().do_thing(MagicMock())

        # THEN it returns an error dict that includes the exception type
        assert result["error"] == "bad input"
        assert result["error_type"] == "ValueError"

    async def test_given_context_key_passed_positionally_when_error_then_includes_key_in_response(
        self,
    ):
        # GIVEN a service method decorated with error_context_keys=("project_id",)
        class Svc:
            @error_boundary(error_context_keys=("project_id",))
            async def do_thing(self, ctx, project_id):
                raise RuntimeError("boom")

        # WHEN it raises and project_id was passed as a positional arg
        result = await Svc().do_thing(MagicMock(), "syn123")

        # THEN the error response includes the project_id for debugging
        assert result["project_id"] == "syn123"
        assert result["error"] == "boom"

    async def test_given_context_key_passed_as_kwarg_when_error_then_includes_key_in_response(
        self,
    ):
        # GIVEN a service method decorated with error_context_keys=("task_id",)
        class Svc:
            @error_boundary(error_context_keys=("task_id",))
            async def do_thing(self, ctx, task_id):
                raise RuntimeError("boom")

        # WHEN it raises and task_id was passed as a keyword arg
        result = await Svc().do_thing(MagicMock(), task_id=7)

        # THEN the error response includes the task_id for debugging
        assert result["task_id"] == 7

    async def test_given_wrap_errors_list_when_error_then_wraps_error_dict_in_list(self):
        # GIVEN a service method decorated with wrap_errors=True
        class Svc:
            @error_boundary(wrap_errors=True)
            async def do_thing(self, ctx):
                raise RuntimeError("boom")

        # WHEN the method raises
        result = await Svc().do_thing(MagicMock())

        # THEN the error dict is wrapped in a list
        assert isinstance(result, list)
        assert result[0]["error"] == "boom"

    async def test_given_wrap_errors_list_and_context_keys_when_auth_error_then_wraps_with_context(
        self,
    ):
        # GIVEN a list-returning service method with context keys
        class Svc:
            @error_boundary(
                error_context_keys=("project_id",),
                wrap_errors=True,
            )
            async def do_thing(self, ctx, project_id):
                raise ConnectionAuthError("expired")

        # WHEN it raises a ConnectionAuthError
        result = await Svc().do_thing(MagicMock(), "syn123")

        # THEN the error is wrapped in a list and includes context
        assert isinstance(result, list)
        assert "Authentication required" in result[0]["error"]
        assert result[0]["project_id"] == "syn123"

    async def test_given_wrap_errors_list_when_success_then_returns_list_unwrapped(self):
        # GIVEN a service method that returns a list successfully
        class Svc:
            @error_boundary(wrap_errors=True)
            async def do_thing(self, ctx):
                return [{"data": 1}, {"data": 2}]

        # WHEN the method succeeds
        result = await Svc().do_thing(MagicMock())

        # THEN the original list is returned as-is (not double-wrapped)
        assert result == [{"data": 1}, {"data": 2}]

    async def test_given_auth_error_when_called_then_error_dict_includes_error_type(self):
        # GIVEN a service method that raises ConnectionAuthError
        class Svc:
            @error_boundary()
            async def do_thing(self, ctx):
                raise ConnectionAuthError("expired")

        # WHEN the method is called
        result = await Svc().do_thing(MagicMock())

        # THEN the error dict includes the error_type key
        assert result["error_type"] == "ConnectionAuthError"


# -------------------------------------------------------------------
# dataclass_to_dict
# -------------------------------------------------------------------


class TestDataclassToDict:
    def test_given_simple_dataclass_then_returns_dict_with_all_fields(self):
        # GIVEN a simple dataclass instance
        @dataclass
        class Item:
            name: str = "test"
            value: int = 42

        obj = Item()

        # WHEN converted
        result = dataclass_to_dict(obj)

        # THEN all fields are included
        assert result == {"name": "test", "value": 42}

    def test_given_nested_dataclass_then_recursively_serializes(self):
        # GIVEN a dataclass with a nested dataclass field
        @dataclass
        class Inner:
            x: int = 1

        @dataclass
        class Outer:
            inner: Inner = None
            label: str = "outer"

        obj = Outer(inner=Inner(x=99), label="test")

        # WHEN converted
        result = dataclass_to_dict(obj)

        # THEN the nested dataclass is also serialized to a dict
        assert result == {"inner": {"x": 99}, "label": "test"}

    def test_given_field_with_repr_false_then_field_is_excluded(self):
        # GIVEN a dataclass with a repr=False field
        @dataclass
        class WithHidden:
            visible: str = "yes"
            _internal: str = field(default="hidden", repr=False)

        obj = WithHidden()

        # WHEN converted
        result = dataclass_to_dict(obj)

        # THEN the repr=False field is excluded
        assert result == {"visible": "yes"}
        assert "_internal" not in result

    def test_given_none_then_returns_none(self):
        # GIVEN None
        # WHEN converted
        result = dataclass_to_dict(None)

        # THEN None is returned
        assert result is None

    def test_given_non_dataclass_then_returns_object_unchanged(self):
        # GIVEN a plain string
        # WHEN converted
        result = dataclass_to_dict("hello")

        # THEN the string is returned as-is
        assert result == "hello"

    def test_given_nested_none_field_then_none_is_preserved(self):
        # GIVEN a dataclass with a None field that could be a nested dataclass
        @dataclass
        class Parent:
            child: object = None
            name: str = "parent"

        obj = Parent()

        # WHEN converted
        result = dataclass_to_dict(obj)

        # THEN the None field is preserved
        assert result == {"child": None, "name": "parent"}

    def test_given_underscore_field_then_field_is_excluded(self):
        # GIVEN a dataclass with a field starting with _
        @dataclass
        class WithInternal:
            name: str = "visible"
            _cache: str = "hidden"

        obj = WithInternal()

        # WHEN converted
        result = dataclass_to_dict(obj)

        # THEN the _ field is excluded
        assert result == {"name": "visible"}
        assert "_cache" not in result

    def test_given_dict_with_dataclass_values_then_recursively_serializes(self):
        # GIVEN a dict containing a dataclass value
        @dataclass
        class Item:
            x: int = 1

        obj = {"key": Item(x=42), "plain": "text"}

        # WHEN converted
        result = dataclass_to_dict(obj)

        # THEN the dict values are recursively serialized
        assert result == {"key": {"x": 42}, "plain": "text"}

    def test_given_list_with_dataclass_items_then_recursively_serializes(self):
        # GIVEN a list containing dataclass items
        @dataclass
        class Item:
            x: int = 1

        obj = [Item(x=1), Item(x=2)]

        # WHEN converted
        result = dataclass_to_dict(obj)

        # THEN each item is serialized
        assert result == [{"x": 1}, {"x": 2}]
