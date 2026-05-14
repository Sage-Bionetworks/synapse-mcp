"""Tests for SchemaOrganizationService."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.schema_organization_service import (
    SchemaOrganizationService,
)

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"


TS = "synapse_mcp.services.tool_service"
SVC = "synapse_mcp.services.schema_organization_service"


@dataclass
class FakeOrg:
    name: str = "sage.example"
    id: str = "42"
    created_on: str = "2025-01-01"
    created_by: str = "user1"


@dataclass
class FakeSchema:
    name: str = "ExampleSchema"
    organization_name: str = "sage.example"
    organization_id: int = 42
    id: str = "sage.example-ExampleSchema"
    created_on: str = "2025-01-01"
    created_by: str = "user1"
    uri: str = "http://example/schema"


@dataclass
class FakeVersion:
    semantic_version: str = "1.0.0"
    created_on: str = "2025-01-01"
    json_sha256_hex: str = "deadbeef"


class TestGetSchemaOrganization:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.SchemaOrganization")
    async def test_given_organization_name_when_get_then_returns_serialized_org(
        self, mock_org_cls: MagicMock, mock_get_client: AsyncMock
    ):
        """Fetching by organization_name returns the serialized org and constructs SchemaOrganization with name=."""
        # GIVEN an organization fetched by name
        mock_get_client.return_value = MagicMock()
        mock_org_cls.return_value.get_async = AsyncMock(
            return_value=FakeOrg(name="sage.example", id="42")
        )

        # WHEN we get the organization by name
        result = await SchemaOrganizationService().get_schema_organization(
            MagicMock(), organization_name="sage.example"
        )

        # THEN organization metadata is returned
        assert "name" in result
        assert result["name"] == "sage.example"
        assert "id" in result
        assert result["id"] == "42"
        mock_org_cls.assert_called_once_with(name="sage.example")

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_when_called_then_returns_error_dict(
        self, mock_get_client: AsyncMock
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError("expired")

        # WHEN we get the organization
        result = await SchemaOrganizationService().get_schema_organization(
            MagicMock(), organization_name="sage.example"
        )

        # THEN the auth error is returned with organization_name context
        assert isinstance(result, dict)
        assert "Authentication required" in result["error"]
        assert result["organization_name"] == "sage.example"


class TestGetSchemaOrganizationAcl:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.SchemaOrganization")
    async def test_given_organization_when_get_acl_then_returns_serialized_acl(
        self, mock_org_cls: MagicMock, mock_get_client: AsyncMock
    ):
        """get_schema_organization_acl returns the serialized ACL directly."""
        # GIVEN an organization with an ACL
        mock_get_client.return_value = MagicMock()
        mock_org_cls.return_value.get_async = AsyncMock(
            return_value=FakeOrg(name="sage.example", id="42")
        )
        mock_org_cls.return_value.get_acl_async = AsyncMock(
            return_value={"resource_access": [], "etag": "acl-etag"}
        )

        # WHEN we get the ACL
        result = await SchemaOrganizationService().get_schema_organization_acl(
            MagicMock(), organization_name="sage.example"
        )

        # THEN the ACL fields are returned at the top level
        assert "etag" in result
        assert result["etag"] == "acl-etag"
        assert "resource_access" in result
        assert result["resource_access"] == []
        mock_org_cls.assert_called_once_with(name="sage.example")
        # get_async must be called before get_acl_async to populate org.id
        mock_org_cls.return_value.get_async.assert_awaited_once()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_when_called_then_returns_error_dict(
        self, mock_get_client: AsyncMock
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError("expired")

        # WHEN we get the ACL
        result = await SchemaOrganizationService().get_schema_organization_acl(
            MagicMock(), organization_name="sage.example"
        )

        # THEN the auth error is returned with organization_name context
        assert isinstance(result, dict)
        assert "Authentication required" in result["error"]
        assert result["organization_name"] == "sage.example"


class TestListJsonSchemas:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.SchemaOrganization")
    async def test_given_organization_when_listed_then_returns_all_schemas(
        self, mock_org_cls: MagicMock, mock_get_client: AsyncMock
    ):
        """list_json_schemas serializes every schema yielded by the SDK iterator into the result list."""
        # GIVEN an organization with two schemas
        mock_get_client.return_value = MagicMock()

        async def _schemas(**_):
            yield FakeSchema(name="SchemaA")
            yield FakeSchema(name="SchemaB")

        mock_org_cls.return_value.get_json_schemas_async = _schemas

        # WHEN we list schemas
        result = await SchemaOrganizationService().list_json_schemas(
            MagicMock(), organization_name="sage.example"
        )

        # THEN both schemas are returned as dicts
        assert len(result) == 2
        assert "name" in result[0]
        assert result[0]["name"] == "SchemaA"
        assert "name" in result[1]
        assert result[1]["name"] == "SchemaB"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.SchemaOrganization")
    async def test_given_limit_when_listed_then_stops_at_limit(
        self, mock_org_cls: MagicMock, mock_get_client: AsyncMock
    ):
        """list_json_schemas honors the limit and stops iterating the SDK generator early."""
        # GIVEN an organization that would yield five schemas
        mock_get_client.return_value = MagicMock()
        fetched: list[str] = []

        async def _schemas(**_):
            for i in range(5):
                fetched.append(f"Schema{i}")
                yield FakeSchema(name=f"Schema{i}")

        mock_org_cls.return_value.get_json_schemas_async = _schemas

        # WHEN we list with limit=2
        result = await SchemaOrganizationService().list_json_schemas(
            MagicMock(), organization_name="sage.example", limit=2
        )

        # THEN only two are returned AND the SDK is not iterated past the limit
        assert len(result) == 2
        assert result[0]["name"] == "Schema0"
        assert result[1]["name"] == "Schema1"
        assert fetched == ["Schema0", "Schema1"]

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_when_called_then_returns_error_list(
        self, mock_get_client: AsyncMock
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError("expired")

        # WHEN we list schemas
        result = await SchemaOrganizationService().list_json_schemas(
            MagicMock(), organization_name="sage.example"
        )

        # THEN the auth error is wrapped in a list with organization_name context
        assert isinstance(result, list)
        assert "Authentication required" in result[0]["error"]
        assert result[0]["organization_name"] == "sage.example"


class TestGetJsonSchema:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.JSONSchema")
    async def test_given_organization_and_schema_name_when_get_then_returns_metadata(
        self, mock_schema_cls: MagicMock, mock_get_client: AsyncMock
    ):
        """get_json_schema returns serialized metadata and constructs JSONSchema with both organization_name and name."""
        # GIVEN a schema with known metadata
        mock_get_client.return_value = MagicMock()
        mock_schema_cls.return_value.get_async = AsyncMock(
            return_value=FakeSchema(
                name="ExampleSchema",
                organization_name="sage.example",
            )
        )

        # WHEN we get the schema
        result = await SchemaOrganizationService().get_json_schema(
            MagicMock(),
            organization_name="sage.example",
            schema_name="ExampleSchema",
        )

        # THEN the metadata is returned
        assert "name" in result
        assert result["name"] == "ExampleSchema"
        assert "organization_name" in result
        assert result["organization_name"] == "sage.example"
        mock_schema_cls.assert_called_once_with(
            organization_name="sage.example",
            name="ExampleSchema",
        )

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_when_called_then_returns_error_dict(
        self, mock_get_client: AsyncMock
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError("expired")

        # WHEN we get the schema
        result = await SchemaOrganizationService().get_json_schema(
            MagicMock(),
            organization_name="sage.example",
            schema_name="ExampleSchema",
        )

        # THEN the auth error is returned with organization_name and schema_name context
        assert isinstance(result, dict)
        assert "Authentication required" in result["error"]
        assert result["organization_name"] == "sage.example"
        assert result["schema_name"] == "ExampleSchema"


class TestGetJsonSchemaBody:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.JSONSchema")
    async def test_given_no_version_when_get_body_then_forwards_version_none(
        self, mock_schema_cls: MagicMock, mock_get_client: AsyncMock
    ):
        """get_json_schema_body returns the raw JSON body and forwards version=None when no version is given."""
        # GIVEN a schema with a JSON body
        mock_get_client.return_value = MagicMock()
        body = {"$id": "schema-id", "type": "object", "properties": {}}
        mock_schema_cls.return_value.get_body_async = AsyncMock(return_value=body)

        # WHEN we get the schema body without a version
        result = await SchemaOrganizationService().get_json_schema_body(
            MagicMock(),
            organization_name="sage.example",
            schema_name="ExampleSchema",
        )

        # THEN the body is returned as a dict
        assert "$id" in result
        assert result["$id"] == "schema-id"
        assert "type" in result
        assert result["type"] == "object"
        mock_schema_cls.return_value.get_body_async.assert_awaited_once()
        kwargs = mock_schema_cls.return_value.get_body_async.call_args.kwargs
        assert "version" in kwargs
        assert kwargs["version"] is None

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.JSONSchema")
    async def test_given_version_when_get_body_then_forwards_version(
        self, mock_schema_cls: MagicMock, mock_get_client: AsyncMock
    ):
        """An explicit version argument is forwarded verbatim to JSONSchema.get_body_async."""
        # GIVEN a request for a specific version
        mock_get_client.return_value = MagicMock()
        mock_schema_cls.return_value.get_body_async = AsyncMock(return_value={})

        # WHEN we get the schema body with a version
        await SchemaOrganizationService().get_json_schema_body(
            MagicMock(),
            organization_name="sage.example",
            schema_name="ExampleSchema",
            version="1.2.3",
        )

        # THEN the version is forwarded to the SDK call
        kwargs = mock_schema_cls.return_value.get_body_async.call_args.kwargs
        assert "version" in kwargs
        assert kwargs["version"] == "1.2.3"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_when_called_then_returns_error_dict(
        self, mock_get_client: AsyncMock
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError("expired")

        # WHEN we get the schema body
        result = await SchemaOrganizationService().get_json_schema_body(
            MagicMock(),
            organization_name="sage.example",
            schema_name="ExampleSchema",
        )

        # THEN the auth error is returned with organization_name and schema_name context
        assert isinstance(result, dict)
        assert "Authentication required" in result["error"]
        assert result["organization_name"] == "sage.example"
        assert result["schema_name"] == "ExampleSchema"


class TestListJsonSchemaVersions:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.JSONSchema")
    async def test_given_schema_when_list_versions_then_returns_all_in_order(
        self, mock_schema_cls: MagicMock, mock_get_client: AsyncMock
    ):
        """list_json_schema_versions serializes each version yielded by the SDK iterator in iteration order."""
        # GIVEN a schema with multiple versions
        mock_get_client.return_value = MagicMock()

        async def _versions(**_):
            yield FakeVersion(semantic_version="1.0.0")
            yield FakeVersion(semantic_version="2.0.0")

        mock_schema_cls.return_value.get_versions_async = _versions

        # WHEN we list versions
        result = await SchemaOrganizationService().list_json_schema_versions(
            MagicMock(),
            organization_name="sage.example",
            schema_name="ExampleSchema",
        )

        # THEN all versions are returned in order
        assert len(result) == 2
        assert "semantic_version" in result[0]
        assert result[0]["semantic_version"] == "1.0.0"
        assert "semantic_version" in result[1]
        assert result[1]["semantic_version"] == "2.0.0"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.JSONSchema")
    async def test_given_limit_when_listed_then_stops_at_limit(
        self, mock_schema_cls: MagicMock, mock_get_client: AsyncMock
    ):
        """list_json_schema_versions honors the limit and stops iterating the SDK generator early."""
        # GIVEN a schema that would yield four versions
        mock_get_client.return_value = MagicMock()
        fetched: list[str] = []

        async def _versions(**_):
            for v in ["1.0.0", "2.0.0", "3.0.0", "4.0.0"]:
                fetched.append(v)
                yield FakeVersion(semantic_version=v)

        mock_schema_cls.return_value.get_versions_async = _versions

        # WHEN we list with limit=1
        result = await SchemaOrganizationService().list_json_schema_versions(
            MagicMock(),
            organization_name="sage.example",
            schema_name="ExampleSchema",
            limit=1,
        )

        # THEN only one is returned AND the SDK is not iterated past the limit
        assert len(result) == 1
        assert result[0]["semantic_version"] == "1.0.0"
        assert fetched == ["1.0.0"]

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_when_called_then_returns_error_list(
        self, mock_get_client: AsyncMock
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError("expired")

        # WHEN we list versions
        result = await SchemaOrganizationService().list_json_schema_versions(
            MagicMock(),
            organization_name="sage.example",
            schema_name="ExampleSchema",
        )

        # THEN the auth error is wrapped in a list with organization_name and schema_name context
        assert isinstance(result, list)
        assert "Authentication required" in result[0]["error"]
        assert result[0]["organization_name"] == "sage.example"
        assert result[0]["schema_name"] == "ExampleSchema"

