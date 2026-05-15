"""Tests for synapse_client, @error_boundary, serialize_model, dataclass_to_dict, and collect_generator."""

import enum
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.tool_service import (
    collect_generator,
    dataclass_to_dict,
    error_boundary,
    serialize_model,
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
        @error_boundary()
        async def do_thing(ctx):
            return {"data": 42}

        # WHEN the method is called
        result = await do_thing(MagicMock())

        # THEN the original return value passes through
        assert result == {"data": 42}

    async def test_given_auth_error_when_called_then_returns_error_dict(self):
        # GIVEN a service method that raises ConnectionAuthError
        @error_boundary()
        async def do_thing(ctx):
            raise ConnectionAuthError("expired")

        # WHEN the method is called
        result = await do_thing(MagicMock())

        # THEN it returns an error dict with "Authentication required" message
        assert "Authentication required" in result["error"]

    async def test_given_generic_exception_when_called_then_returns_error_with_type(self):
        # GIVEN a service method that raises a ValueError
        @error_boundary()
        async def do_thing(ctx):
            raise ValueError("bad input")

        # WHEN the method is called
        result = await do_thing(MagicMock())

        # THEN it returns an error dict that includes the exception type
        assert result["error"] == "bad input"
        assert result["error_type"] == "ValueError"

    async def test_given_context_key_passed_positionally_when_error_then_includes_key_in_response(
        self,
    ):
        # GIVEN a service method decorated with error_context_keys=("project_id",)
        @error_boundary(error_context_keys=("project_id",))
        async def do_thing(ctx, project_id):
            raise RuntimeError("boom")

        # WHEN it raises and project_id was passed as a positional arg
        result = await do_thing(MagicMock(), "syn123")

        # THEN the error response includes the project_id for debugging
        assert result["project_id"] == "syn123"
        assert result["error"] == "boom"

    async def test_given_context_key_passed_as_kwarg_when_error_then_includes_key_in_response(
        self,
    ):
        # GIVEN a service method decorated with error_context_keys=("task_id",)
        @error_boundary(error_context_keys=("task_id",))
        async def do_thing(ctx, task_id):
            raise RuntimeError("boom")

        # WHEN it raises and task_id was passed as a keyword arg
        result = await do_thing(MagicMock(), task_id=7)

        # THEN the error response includes the task_id for debugging
        assert result["task_id"] == 7

    async def test_given_wrap_errors_list_when_error_then_wraps_error_dict_in_list(self):
        # GIVEN a service method decorated with wrap_errors=True
        @error_boundary(wrap_errors=True)
        async def do_thing(ctx):
            raise RuntimeError("boom")

        # WHEN the method raises
        result = await do_thing(MagicMock())

        # THEN the error dict is wrapped in a list
        assert isinstance(result, list)
        assert result[0]["error"] == "boom"

    async def test_given_wrap_errors_list_and_context_keys_when_auth_error_then_wraps_with_context(
        self,
    ):
        # GIVEN a list-returning service method with context keys
        @error_boundary(
            error_context_keys=("project_id",),
            wrap_errors=True,
        )
        async def do_thing(ctx, project_id):
            raise ConnectionAuthError("expired")

        # WHEN it raises a ConnectionAuthError
        result = await do_thing(MagicMock(), "syn123")

        # THEN the error is wrapped in a list and includes context
        assert isinstance(result, list)
        assert "Authentication required" in result[0]["error"]
        assert result[0]["project_id"] == "syn123"

    async def test_given_wrap_errors_list_when_success_then_returns_list_unwrapped(self):
        # GIVEN a service method that returns a list successfully
        @error_boundary(wrap_errors=True)
        async def do_thing(ctx):
            return [{"data": 1}, {"data": 2}]

        # WHEN the method succeeds
        result = await do_thing(MagicMock())

        # THEN the original list is returned as-is (not double-wrapped)
        assert result == [{"data": 1}, {"data": 2}]

    async def test_given_static_method_on_class_when_called_then_passes_args_through(self):
        # GIVEN a service-shaped class that uses @staticmethod with @error_boundary
        # (this is the production pattern since DPE-1623 — services hold no state).
        class Svc:
            @staticmethod
            @error_boundary(error_context_keys=("project_id",))
            async def do_thing(ctx, project_id):
                return {"project_id": project_id, "data": "ok"}

        # WHEN called via the class (no instance) and via an instance
        result_via_class = await Svc.do_thing(MagicMock(), "syn123")
        result_via_instance = await Svc().do_thing(MagicMock(), "syn456")

        # THEN both invocation styles work and the wrapper does NOT swallow ctx as self
        assert result_via_class == {"project_id": "syn123", "data": "ok"}
        assert result_via_instance == {"project_id": "syn456", "data": "ok"}


# -------------------------------------------------------------------
# serialize_model
# -------------------------------------------------------------------


class TestSerializeModel:
    def test_given_dataclass_then_returns_public_repr_fields(
        self,
    ):
        # GIVEN a dataclass with public and private fields
        @dataclass
        class Sample:
            id: str = "syn1"
            name: str = "test"
            _private: str = field(
                default="hidden", repr=False
            )
            config: str = field(
                default="skip", repr=False
            )

        # WHEN serialized
        result = serialize_model(Sample())

        # THEN only public repr=True fields are included
        assert result == {"id": "syn1", "name": "test"}
        assert "_private" not in result
        assert "config" not in result

    def test_given_nested_dataclass_then_serializes_recursively(
        self,
    ):
        # GIVEN a dataclass containing another dataclass
        @dataclass
        class Inner:
            value: int = 42

        @dataclass
        class Outer:
            name: str = "parent"
            child: Optional[Inner] = None

        # WHEN serialized with a nested child
        result = serialize_model(
            Outer(child=Inner(value=99))
        )

        # THEN the nested dataclass is also serialized
        assert result["child"] == {"value": 99}

    def test_given_list_of_dataclasses_then_serializes_each(
        self,
    ):
        # GIVEN a list of dataclasses
        @dataclass
        class Item:
            id: int = 0

        # WHEN serialized
        result = serialize_model(
            [Item(id=1), Item(id=2)]
        )

        # THEN each item is serialized
        assert result == [{"id": 1}, {"id": 2}]

    def test_given_dict_then_serializes_values(self):
        # GIVEN a dict with mixed values
        # WHEN serialized
        result = serialize_model(
            {"key": "val", "num": 42}
        )

        # THEN the dict is passed through
        assert result == {"key": "val", "num": 42}

    def test_given_datetime_then_returns_isoformat(self):
        # GIVEN a datetime
        dt = datetime(2025, 1, 15, 12, 30, 0)

        # WHEN serialized
        result = serialize_model(dt)

        # THEN it returns an ISO format string
        assert result == "2025-01-15T12:30:00"

    def test_given_date_then_returns_isoformat(self):
        # GIVEN a date
        d = date(2025, 6, 1)

        # WHEN serialized
        result = serialize_model(d)

        # THEN it returns an ISO format string
        assert result == "2025-06-01"

    def test_given_none_then_returns_none(self):
        assert serialize_model(None) is None

    def test_given_primitives_then_returns_unchanged(self):
        assert serialize_model("hello") == "hello"
        assert serialize_model(42) == 42
        assert serialize_model(3.14) == 3.14
        assert serialize_model(True) is True

    def test_given_legacy_object_with_to_dict_then_uses_it(
        self,
    ):
        # GIVEN a non-dataclass object with to_dict
        class Legacy:
            def to_dict(self):
                return {"legacy": True}

        # WHEN serialized
        result = serialize_model(Legacy())

        # THEN to_dict() is used
        assert result == {"legacy": True}

    def test_given_enum_then_returns_value(self):
        # GIVEN an Enum instance
        class Status(enum.Enum):
            ACTIVE = "active"
            ARCHIVED = "archived"

        # WHEN serialized
        result = serialize_model(Status.ACTIVE)

        # THEN the enum's .value is returned (not str(enum))
        assert result == "active"

    def test_given_custom_mapping_then_serializes_values(self):
        # GIVEN a non-dict Mapping subclass (legacy synapseclient entities
        # are MutableMapping, not dict)
        from collections.abc import Mapping

        class FakeEntityMapping(Mapping):
            def __init__(self, data):
                self._data = data

            def __getitem__(self, key):
                return self._data[key]

            def __iter__(self):
                return iter(self._data)

            def __len__(self):
                return len(self._data)

        mapping = FakeEntityMapping(
            {"id": "syn1", "created": datetime(2025, 1, 15, 12, 0, 0)}
        )

        # WHEN serialized
        result = serialize_model(mapping)

        # THEN values serialize recursively (datetime -> isoformat)
        assert result == {"id": "syn1", "created": "2025-01-15T12:00:00"}

    def test_given_to_dict_returning_nested_types_then_recurses(self):
        # GIVEN an object whose to_dict() returns non-JSON-safe nested types
        class Status(enum.Enum):
            ACTIVE = "active"

        class Legacy:
            def to_dict(self):
                return {
                    "status": Status.ACTIVE,
                    "created": datetime(2025, 3, 15, 9, 0),
                }

        # WHEN serialized
        result = serialize_model(Legacy())

        # THEN the nested Enum/datetime values are also serialized
        assert result == {
            "status": "active",
            "created": "2025-03-15T09:00:00",
        }

    def test_given_non_callable_to_dict_attribute_then_falls_back_to_str(self):
        # GIVEN an object with a ``to_dict`` attribute that isn't a method
        class WeirdAttr:
            to_dict = "not callable"

        obj = WeirdAttr()

        # WHEN serialized
        result = serialize_model(obj)

        # THEN str fallback is used (the attribute is not invoked)
        assert result == str(obj)

    def test_given_unserializable_object_then_falls_back_to_str(self):
        # GIVEN an object with no dataclass, Mapping, or to_dict support
        class Plain:
            def __str__(self):
                return "plain-repr"

        # WHEN serialized
        result = serialize_model(Plain())

        # THEN str() is used
        assert result == "plain-repr"


# -------------------------------------------------------------------
# dataclass_to_dict enhancements
# -------------------------------------------------------------------


class TestDataclassToDict:
    def test_given_datetime_then_returns_isoformat(self):
        dt = datetime(2025, 1, 15, 12, 30, 0)
        result = dataclass_to_dict(dt)
        assert result == "2025-01-15T12:30:00"

    def test_given_date_then_returns_isoformat(self):
        d = date(2025, 6, 1)
        result = dataclass_to_dict(d)
        assert result == "2025-06-01"

    def test_given_enum_then_returns_value(self):
        class Color(enum.Enum):
            RED = "red"
            BLUE = "blue"

        result = dataclass_to_dict(Color.RED)
        assert result == "red"

    def test_given_dataclass_with_enum_field_then_extracts_value(self):
        class Status(enum.Enum):
            ACTIVE = "active"
            ARCHIVED = "archived"

        @dataclass
        class Item:
            name: str = "test"
            status: Status = Status.ACTIVE

        result = dataclass_to_dict(Item())
        assert result["status"] == "active"

    def test_given_dataclass_with_datetime_field_then_converts(self):
        @dataclass
        class Event:
            name: str = "meeting"
            created_at: datetime = None

        event = Event(created_at=datetime(2025, 3, 15, 9, 0))
        result = dataclass_to_dict(event)
        assert result["created_at"] == "2025-03-15T09:00:00"

    def test_given_nested_dataclass_then_serializes_recursively(self):
        @dataclass
        class Inner:
            value: int = 42

        @dataclass
        class Outer:
            name: str = "parent"
            child: Optional[Inner] = None

        result = dataclass_to_dict(Outer(child=Inner(value=99)))
        assert result["child"] == {"value": 99}

    def test_given_list_of_dataclasses_in_field_then_serializes_each(self):
        @dataclass
        class Item:
            id: int = 0

        @dataclass
        class Container:
            items: List[Item] = field(default_factory=list)

        container = Container(items=[Item(id=1), Item(id=2)])
        result = dataclass_to_dict(container)
        assert result["items"] == [{"id": 1}, {"id": 2}]

    def test_given_none_then_returns_none(self):
        assert dataclass_to_dict(None) is None

    def test_given_primitives_then_returns_unchanged(self):
        assert dataclass_to_dict("hello") == "hello"
        assert dataclass_to_dict(42) == 42
        assert dataclass_to_dict(3.14) == 3.14
        assert dataclass_to_dict(True) is True


# -------------------------------------------------------------------
# collect_generator
# -------------------------------------------------------------------


class TestCollectGenerator:
    def test_given_generator_under_limit_then_collects_all(self):
        gen = iter([1, 2, 3])
        result = collect_generator(gen, limit=10)
        assert result == [1, 2, 3]

    def test_given_generator_over_limit_then_truncates(self):
        gen = iter(range(100))
        result = collect_generator(gen, limit=5)
        assert result == [0, 1, 2, 3, 4]

    def test_given_empty_generator_then_returns_empty_list(self):
        gen = iter([])
        result = collect_generator(gen, limit=10)
        assert result == []

    def test_given_limit_zero_then_returns_empty_list_without_consuming(self):
        gen = iter([1, 2, 3])
        result = collect_generator(gen, limit=0)
        assert result == []
        # The generator must not have been consumed.
        assert next(gen) == 1

    def test_given_negative_limit_then_raises_value_error(self):
        with pytest.raises(ValueError):
            collect_generator(iter([1, 2]), limit=-1)

    def test_given_limit_one_then_returns_exactly_one_item(self):
        gen = iter([10, 20, 30])
        result = collect_generator(gen, limit=1)
        assert result == [10]

    def test_given_limit_truncates_then_does_not_overconsume(self):
        # Regression: the previous `for item in gen; append; check`
        # pattern pulled limit+1 items from the iterator.
        gen = iter([1, 2, 3, 4, 5])
        result = collect_generator(gen, limit=2)
        assert result == [1, 2]
        # The next unread item should still be reachable.
        assert next(gen) == 3


# -------------------------------------------------------------------
# error_boundary — SynapseHTTPError status_code extraction
# -------------------------------------------------------------------


class TestErrorBoundarySynapseHTTPError:
    async def test_given_exception_with_response_status_code_then_includes_it(self):
        class FakeResponse:
            status_code = 404

        @error_boundary()
        async def do_thing(ctx):
            exc = RuntimeError("Not Found")
            exc.response = FakeResponse()
            raise exc

        result = await do_thing(MagicMock())
        assert result["status_code"] == 404
        assert result["error"] == "Not Found"

    async def test_given_exception_without_response_then_no_status_code(self):
        @error_boundary()
        async def do_thing(ctx):
            raise ValueError("bad input")

        result = await do_thing(MagicMock())
        assert "status_code" not in result
        assert result["error"] == "bad input"
