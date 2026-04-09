"""Tests for synapse_client, @error_boundary, serialize_model, dataclass_to_dict, and collect_generator."""

import enum
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.tool_service import (
    collect_generator,
    dataclass_to_dict,
    error_boundary,
    serialize_model,
    synapse_client,
)


# -------------------------------------------------------------------
# synapse_client context manager
# -------------------------------------------------------------------


@patch("synapse_mcp.services.tool_service.get_synapse_client")
class TestSynapseClient:
    def test_given_valid_ctx_when_entering_context_then_yields_authenticated_client(
        self, mock_get_client
    ):
        # GIVEN a request context that resolves to a valid Synapse client
        expected_client = MagicMock()
        mock_get_client.return_value = expected_client
        ctx = MagicMock()

        # WHEN we enter the synapse_client context
        with synapse_client(ctx) as client:
            # THEN it yields the authenticated client
            assert client is expected_client
        mock_get_client.assert_called_once_with(ctx)

    def test_given_expired_credentials_when_entering_context_then_raises_auth_error(
        self, mock_get_client
    ):
        # GIVEN a request context with expired credentials
        mock_get_client.side_effect = ConnectionAuthError("expired")
        ctx = MagicMock()

        # WHEN we enter the synapse_client context
        # THEN it raises ConnectionAuthError
        with pytest.raises(ConnectionAuthError):
            with synapse_client(ctx):
                pass


# -------------------------------------------------------------------
# @error_boundary decorator
# -------------------------------------------------------------------


class TestErrorBoundary:
    def test_given_successful_method_when_called_then_returns_result_unchanged(self):
        # GIVEN a service method that succeeds
        class Svc:
            @error_boundary()
            def do_thing(self, ctx):
                return {"data": 42}

        # WHEN the method is called
        result = Svc().do_thing(MagicMock())

        # THEN the original return value passes through
        assert result == {"data": 42}

    def test_given_auth_error_when_called_then_returns_error_dict(self):
        # GIVEN a service method that raises ConnectionAuthError
        class Svc:
            @error_boundary()
            def do_thing(self, ctx):
                raise ConnectionAuthError("expired")

        # WHEN the method is called
        result = Svc().do_thing(MagicMock())

        # THEN it returns an error dict with "Authentication required" message
        assert "Authentication required" in result["error"]

    def test_given_generic_exception_when_called_then_returns_error_with_type(self):
        # GIVEN a service method that raises a ValueError
        class Svc:
            @error_boundary()
            def do_thing(self, ctx):
                raise ValueError("bad input")

        # WHEN the method is called
        result = Svc().do_thing(MagicMock())

        # THEN it returns an error dict that includes the exception type
        assert result["error"] == "bad input"
        assert result["error_type"] == "ValueError"

    def test_given_context_key_passed_positionally_when_error_then_includes_key_in_response(
        self,
    ):
        # GIVEN a service method decorated with error_context_keys=("project_id",)
        class Svc:
            @error_boundary(error_context_keys=("project_id",))
            def do_thing(self, ctx, project_id):
                raise RuntimeError("boom")

        # WHEN it raises and project_id was passed as a positional arg
        result = Svc().do_thing(MagicMock(), "syn123")

        # THEN the error response includes the project_id for debugging
        assert result["project_id"] == "syn123"
        assert result["error"] == "boom"

    def test_given_context_key_passed_as_kwarg_when_error_then_includes_key_in_response(
        self,
    ):
        # GIVEN a service method decorated with error_context_keys=("task_id",)
        class Svc:
            @error_boundary(error_context_keys=("task_id",))
            def do_thing(self, ctx, task_id):
                raise RuntimeError("boom")

        # WHEN it raises and task_id was passed as a keyword arg
        result = Svc().do_thing(MagicMock(), task_id=7)

        # THEN the error response includes the task_id for debugging
        assert result["task_id"] == 7

    def test_given_wrap_errors_list_when_error_then_wraps_error_dict_in_list(self):
        # GIVEN a service method decorated with wrap_errors=True
        class Svc:
            @error_boundary(wrap_errors=True)
            def do_thing(self, ctx):
                raise RuntimeError("boom")

        # WHEN the method raises
        result = Svc().do_thing(MagicMock())

        # THEN the error dict is wrapped in a list
        assert isinstance(result, list)
        assert result[0]["error"] == "boom"

    def test_given_wrap_errors_list_and_context_keys_when_auth_error_then_wraps_with_context(
        self,
    ):
        # GIVEN a list-returning service method with context keys
        class Svc:
            @error_boundary(
                error_context_keys=("project_id",),
                wrap_errors=True,
            )
            def do_thing(self, ctx, project_id):
                raise ConnectionAuthError("expired")

        # WHEN it raises a ConnectionAuthError
        result = Svc().do_thing(MagicMock(), "syn123")

        # THEN the error is wrapped in a list and includes context
        assert isinstance(result, list)
        assert "Authentication required" in result[0]["error"]
        assert result[0]["project_id"] == "syn123"

    def test_given_wrap_errors_list_when_success_then_returns_list_unwrapped(self):
        # GIVEN a service method that returns a list successfully
        class Svc:
            @error_boundary(wrap_errors=True)
            def do_thing(self, ctx):
                return [{"data": 1}, {"data": 2}]

        # WHEN the method succeeds
        result = Svc().do_thing(MagicMock())

        # THEN the original list is returned as-is (not double-wrapped)
        assert result == [{"data": 1}, {"data": 2}]


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


# -------------------------------------------------------------------
# error_boundary — SynapseHTTPError status_code extraction
# -------------------------------------------------------------------


class TestErrorBoundarySynapseHTTPError:
    def test_given_exception_with_response_status_code_then_includes_it(self):
        class FakeResponse:
            status_code = 404

        class Svc:
            @error_boundary()
            def do_thing(self, ctx):
                exc = RuntimeError("Not Found")
                exc.response = FakeResponse()
                raise exc

        result = Svc().do_thing(MagicMock())
        assert result["status_code"] == 404
        assert result["error"] == "Not Found"

    def test_given_exception_without_response_then_no_status_code(self):
        class Svc:
            @error_boundary()
            def do_thing(self, ctx):
                raise ValueError("bad input")

        result = Svc().do_thing(MagicMock())
        assert "status_code" not in result
        assert result["error"] == "bad input"
