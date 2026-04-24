"""Tests for synapse_client, @error_boundary, serialize_model, dataclass_to_dict, and collect_generator."""

import enum
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.tool_service import (
    DEFAULT_DESTRUCTIVE_ANNOTATIONS,
    DEFAULT_READ_ANNOTATIONS,
    DEFAULT_WRITE_ANNOTATIONS,
    collect_generator,
    dataclass_to_dict,
    error_boundary,
    serialize_model,
    service_tool,
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
    async def test_given_exception_with_response_status_code_then_includes_it(self):
        class FakeResponse:
            status_code = 404

        class Svc:
            @error_boundary()
            async def do_thing(self, ctx):
                exc = RuntimeError("Not Found")
                exc.response = FakeResponse()
                raise exc

        result = await Svc().do_thing(MagicMock())
        assert result["status_code"] == 404
        assert result["error"] == "Not Found"

    async def test_given_exception_without_response_then_no_status_code(self):
        class Svc:
            @error_boundary()
            async def do_thing(self, ctx):
                raise ValueError("bad input")

        result = await Svc().do_thing(MagicMock())
        assert "status_code" not in result
        assert result["error"] == "bad input"


# -------------------------------------------------------------------
# service_tool decorator
# -------------------------------------------------------------------


class _FakeMCP:
    """Minimal mcp.tool recorder for unit tests."""

    def __init__(self):
        self.registrations = []

    def tool(self, **kwargs):
        def decorator(fn):
            self.registrations.append({"fn": fn, **kwargs})
            return fn

        return decorator


class TestServiceToolPrefixValidation:
    def test_given_approved_prefix_when_decorating_then_registers(self):
        mcp = _FakeMCP()

        @service_tool(
            mcp,
            service="entity",
            operation="read",
            synapse_object="Synapse entity",
            title="Get Thing",
            description="Use this when the user wants a Synapse entity.",
        )
        async def get_thing():
            return {"ok": True}

        assert len(mcp.registrations) == 1
        assert mcp.registrations[0]["fn"].__name__ == "get_thing"

    def test_given_nonapproved_prefix_when_decorating_then_raises(self):
        mcp = _FakeMCP()

        with pytest.raises(ValueError, match="must start with"):

            @service_tool(
                mcp,
                service="entity",
                operation="read",
                synapse_object="Synapse entity",
                title="Fetch Thing",
                description="Use this when the user wants a Synapse entity.",
            )
            async def fetch_thing():
                return {}

    def test_given_is_prefix_then_rejected(self):
        mcp = _FakeMCP()
        with pytest.raises(ValueError):

            @service_tool(
                mcp,
                service="user",
                operation="read",
                synapse_object="Synapse user",
                title="Is Certified",
                description="Use this when checking a Synapse user is certified.",
            )
            async def is_user_certified():
                return {}


class TestServiceToolSynapseObjectValidation:
    def test_given_synapse_object_missing_from_first_sentence_then_raises(self):
        mcp = _FakeMCP()
        with pytest.raises(ValueError, match="must name the Synapse object"):

            @service_tool(
                mcp,
                service="entity",
                operation="read",
                synapse_object="Synapse entity",
                title="Get Thing",
                description="Use this when the user wants metadata. Works for any object.",
            )
            async def get_thing():
                return {}

    def test_given_synapse_object_case_insensitive_then_passes(self):
        mcp = _FakeMCP()

        @service_tool(
            mcp,
            service="team",
            operation="read",
            synapse_object="Synapse Team",
            title="Get Team",
            description="Use this when the user wants a synapse team by ID.",
        )
        async def get_team():
            return {}

        assert len(mcp.registrations) == 1


class TestServiceToolDescriptionExtensions:
    def test_given_synonyms_when_decorating_then_related_terms_appended(self):
        mcp = _FakeMCP()

        @service_tool(
            mcp,
            service="activity",
            operation="read",
            synapse_object="Synapse activity",
            title="Get Provenance",
            description="Use this when the user wants Synapse activity for an entity.",
            synonyms=("lineage", "history", "inputs"),
        )
        async def get_provenance():
            return {}

        desc = mcp.registrations[0]["description"]
        assert "Related terms: lineage, history, inputs" in desc

    def test_given_siblings_when_decorating_then_distinct_from_appended(self):
        mcp = _FakeMCP()

        @service_tool(
            mcp,
            service="wiki",
            operation="read",
            synapse_object="Synapse wiki",
            title="Get Wiki Headers",
            description="Use this when the user wants the table of contents for a Synapse wiki.",
            siblings=("get_wiki_history", "get_wiki_page"),
        )
        async def get_wiki_headers():
            return {}

        desc = mcp.registrations[0]["description"]
        assert "Distinct from: get_wiki_history, get_wiki_page" in desc

    def test_given_no_synonyms_or_siblings_then_description_unchanged(self):
        mcp = _FakeMCP()

        @service_tool(
            mcp,
            service="entity",
            operation="read",
            synapse_object="Synapse entity",
            title="Get Entity",
            description="Use this when the user wants a Synapse entity.",
        )
        async def get_entity():
            return {}

        assert mcp.registrations[0]["description"] == "Use this when the user wants a Synapse entity."


class TestServiceToolTagging:
    def _register(self, operation, service="entity"):
        mcp = _FakeMCP()

        @service_tool(
            mcp,
            service=service,
            operation=operation,
            synapse_object="Synapse entity",
            title="T",
            description="Use this when the user wants a Synapse entity.",
        )
        async def get_x():
            return {}

        return mcp.registrations[0]

    def test_read_tags_include_readonly_and_service(self):
        reg = self._register("read")
        tags = reg["tags"]
        assert "entity" in tags
        assert "read" in tags
        assert "readonly" in tags
        assert "mutation" not in tags
        assert "destructive" not in tags

    def test_write_tags_include_mutation(self):
        mcp = _FakeMCP()

        @service_tool(
            mcp,
            service="entity",
            operation="write",
            synapse_object="Synapse entity",
            title="U",
            description="Use this when the user wants to update a Synapse entity.",
        )
        async def update_x():
            return {}

        tags = mcp.registrations[0]["tags"]
        assert "write" in tags
        assert "mutation" in tags
        assert "readonly" not in tags
        assert "destructive" not in tags

    def test_destructive_tags_include_mutation_and_destructive(self):
        mcp = _FakeMCP()

        @service_tool(
            mcp,
            service="entity",
            operation="destructive",
            synapse_object="Synapse entity",
            title="D",
            description="Use this when the user wants to delete a Synapse entity.",
        )
        async def delete_x():
            return {}

        tags = mcp.registrations[0]["tags"]
        assert "destructive" in tags
        assert "mutation" in tags
        assert "readonly" not in tags

    def test_admin_tags_include_admin(self):
        mcp = _FakeMCP()

        @service_tool(
            mcp,
            service="team",
            operation="admin",
            synapse_object="Synapse team",
            title="R",
            description="Use this when the user wants to register a Synapse team admin hook.",
        )
        async def register_hook():
            return {}

        tags = mcp.registrations[0]["tags"]
        assert "admin" in tags


class TestServiceToolAnnotations:
    def test_read_operation_uses_readonly_defaults(self):
        mcp = _FakeMCP()

        @service_tool(
            mcp,
            service="entity",
            operation="read",
            synapse_object="Synapse entity",
            title="T",
            description="Use this when the user wants a Synapse entity.",
        )
        async def get_x():
            return {}

        assert mcp.registrations[0]["annotations"] == DEFAULT_READ_ANNOTATIONS

    def test_destructive_operation_uses_destructive_defaults(self):
        mcp = _FakeMCP()

        @service_tool(
            mcp,
            service="entity",
            operation="destructive",
            synapse_object="Synapse entity",
            title="T",
            description="Use this when the user wants to delete a Synapse entity.",
        )
        async def delete_x():
            return {}

        assert mcp.registrations[0]["annotations"] == DEFAULT_DESTRUCTIVE_ANNOTATIONS

    def test_write_operation_uses_write_defaults(self):
        mcp = _FakeMCP()

        @service_tool(
            mcp,
            service="entity",
            operation="write",
            synapse_object="Synapse entity",
            title="T",
            description="Use this when the user wants to update a Synapse entity.",
        )
        async def update_x():
            return {}

        assert mcp.registrations[0]["annotations"] == DEFAULT_WRITE_ANNOTATIONS

    def test_explicit_annotations_override_defaults(self):
        mcp = _FakeMCP()
        custom = {"readOnlyHint": True, "idempotentHint": False, "destructiveHint": False, "openWorldHint": False}

        @service_tool(
            mcp,
            service="entity",
            operation="read",
            synapse_object="Synapse entity",
            title="T",
            description="Use this when the user wants a Synapse entity.",
            annotations=custom,
        )
        async def get_x():
            return {}

        assert mcp.registrations[0]["annotations"] == custom


class TestServiceToolErrorBoundary:
    async def test_tool_raising_auth_error_returns_error_dict(self):
        mcp = _FakeMCP()

        @service_tool(
            mcp,
            service="entity",
            operation="read",
            synapse_object="Synapse entity",
            title="T",
            description="Use this when the user wants a Synapse entity.",
        )
        async def get_x(ctx):
            raise ConnectionAuthError("expired")

        fn = mcp.registrations[0]["fn"]
        result = await fn(MagicMock())
        assert result["error_type"] == "ConnectionAuthError"
        assert "Authentication required" in result["error"]

    async def test_tool_raising_generic_exception_returns_error_dict(self):
        mcp = _FakeMCP()

        @service_tool(
            mcp,
            service="entity",
            operation="read",
            synapse_object="Synapse entity",
            title="T",
            description="Use this when the user wants a Synapse entity.",
        )
        async def get_x(ctx):
            raise ValueError("bad input")

        fn = mcp.registrations[0]["fn"]
        result = await fn(MagicMock())
        assert result["error_type"] == "ValueError"
        assert result["error"] == "bad input"

    async def test_tool_success_passes_through(self):
        mcp = _FakeMCP()

        @service_tool(
            mcp,
            service="entity",
            operation="read",
            synapse_object="Synapse entity",
            title="T",
            description="Use this when the user wants a Synapse entity.",
        )
        async def get_x(ctx):
            return {"id": "syn1"}

        fn = mcp.registrations[0]["fn"]
        result = await fn(MagicMock())
        assert result == {"id": "syn1"}

    async def test_tool_http_error_includes_status_code(self):
        mcp = _FakeMCP()

        class HTTPError(Exception):
            pass

        @service_tool(
            mcp,
            service="entity",
            operation="read",
            synapse_object="Synapse entity",
            title="T",
            description="Use this when the user wants a Synapse entity.",
        )
        async def get_x(ctx):
            err = HTTPError("Not Found")
            err.response = MagicMock(status_code=404)
            raise err

        fn = mcp.registrations[0]["fn"]
        result = await fn(MagicMock())
        assert result["status_code"] == 404
        assert result["error"] == "Not Found"
