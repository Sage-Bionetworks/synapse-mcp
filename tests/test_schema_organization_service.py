"""Tests for SchemaOrganizationService."""

from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    id: int = 42
    created_on: str = "2025-01-01"
    created_by: str = "user1"


@dataclass
class FakeAcl:
    resource_access: Optional[list] = None
    etag: str = "acl-etag"


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
    async def test_get_schema_organization_with_name(
        self, mock_org_cls: MagicMock, mock_get_client: AsyncMock
    ):
        """Fetching by organization_name returns the serialized org and constructs SchemaOrganization with name=."""
        # GIVEN an organization fetched by name
        mock_get_client.return_value = MagicMock()
        mock_org_cls.return_value.get_async = AsyncMock(
            return_value=FakeOrg(name="sage.example", id=42)
        )

        # WHEN we get the organization by name
        result = await SchemaOrganizationService().get_schema_organization(
            MagicMock(), organization_name="sage.example"
        )

        # THEN organization metadata is returned
        assert "name" in result
        assert result["name"] == "sage.example"
        assert "id" in result
        assert result["id"] == 42
        mock_org_cls.assert_called_once_with(name="sage.example")

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.SchemaOrganization")
    async def test_get_schema_organization_with_id(
        self, mock_org_cls: MagicMock, mock_get_client: AsyncMock
    ):
        """Fetching by organization_id constructs SchemaOrganization with id= and not name=."""
        # GIVEN an organization fetched by numeric ID
        mock_get_client.return_value = MagicMock()
        mock_org_cls.return_value.get_async = AsyncMock(
            return_value=FakeOrg(id=99, name="sage.other")
        )

        # WHEN we get the organization by ID
        result = await SchemaOrganizationService().get_schema_organization(
            MagicMock(), organization_id=99
        )

        # THEN organization metadata is returned
        assert "name" in result
        assert result["name"] == "sage.other"
        assert "id" in result
        assert result["id"] == 99
        mock_org_cls.assert_called_once_with(id=99)

    async def test_given_no_name_or_id_then_returns_error(self):
        """Calling get_schema_organization with neither identifier returns an error dict before any SDK call."""
        # GIVEN neither organization_name nor organization_id
        # WHEN we call get_schema_organization
        result = await SchemaOrganizationService().get_schema_organization(
            MagicMock()
        )

        # THEN an error is returned
        assert "error" in result
        assert result["error"] == "Either organization_name or organization_id is required"


class TestGetSchemaOrganizationAcl:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.SchemaOrganization")
    async def test_get_acl(
        self, mock_org_cls: MagicMock, mock_get_client: AsyncMock
    ):
        """get_schema_organization_acl returns the organization name alongside the serialized ACL."""
        # GIVEN an organization with an ACL
        mock_get_client.return_value = MagicMock()
        mock_org_cls.return_value.get_acl_async = AsyncMock(
            return_value=FakeAcl(resource_access=[], etag="acl-etag")
        )

        # WHEN we get the ACL
        result = await SchemaOrganizationService().get_schema_organization_acl(
            MagicMock(), organization_name="sage.example"
        )

        # THEN organization name is returned
        assert "organization_name" in result
        assert result["organization_name"] == "sage.example"


        # AND the ACL is returned
        assert "acl" in result
        assert "etag" in result["acl"]
        assert result["acl"]["etag"] == "acl-etag"
        mock_org_cls.assert_called_once_with(name="sage.example")


class TestListJsonSchemas:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.SchemaOrganization")
    async def test_get_json_schemas(
        self, mock_org_cls: MagicMock, mock_get_client: AsyncMock
    ):
        """list_json_schemas serializes every schema yielded by the SDK iterator into the result list."""
        # GIVEN an organization with two schemas
        mock_get_client.return_value = MagicMock()
        mock_org_cls.return_value.get_json_schemas = MagicMock(
            return_value=iter(
                [
                    FakeSchema(name="SchemaA"),
                    FakeSchema(name="SchemaB"),
                ]
            )
        )

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


class TestGetJsonSchema:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.JSONSchema")
    async def test_get_json_schema(
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


class TestGetJsonSchemaBody:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.JSONSchema")
    async def test_get_body_without_version(
        self, mock_schema_cls: MagicMock, mock_get_client: AsyncMock
    ):
        """get_json_schema_body returns the raw JSON body and forwards version=None when no version is given."""
        # GIVEN a schema with a JSON body
        mock_get_client.return_value = MagicMock()
        body = {"$id": "schema-id", "type": "object", "properties": {}}
        mock_schema_cls.return_value.get_body = MagicMock(return_value=body)

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
        mock_schema_cls.return_value.get_body.assert_called_once()
        kwargs = mock_schema_cls.return_value.get_body.call_args.kwargs
        assert "version" in kwargs
        assert kwargs["version"] is None

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.JSONSchema")
    async def test_get_body_with_version(
        self, mock_schema_cls: MagicMock, mock_get_client: AsyncMock
    ):
        """An explicit version argument is forwarded verbatim to JSONSchema.get_body."""
        # GIVEN a request for a specific version
        mock_get_client.return_value = MagicMock()
        mock_schema_cls.return_value.get_body = MagicMock(return_value={})

        # WHEN we get the schema body with a version
        await SchemaOrganizationService().get_json_schema_body(
            MagicMock(),
            organization_name="sage.example",
            schema_name="ExampleSchema",
            version="1.2.3",
        )

        # THEN the version is forwarded to the SDK call
        kwargs = mock_schema_cls.return_value.get_body.call_args.kwargs
        assert "version" in kwargs
        assert kwargs["version"] == "1.2.3"


class TestListJsonSchemaVersions:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.JSONSchema")
    async def test_get_versions(
        self, mock_schema_cls: MagicMock, mock_get_client: AsyncMock
    ):
        """list_json_schema_versions serializes each version yielded by the SDK iterator in iteration order."""
        # GIVEN a schema with multiple versions
        mock_get_client.return_value = MagicMock()
        mock_schema_cls.return_value.get_versions = MagicMock(
            return_value=iter(
                [
                    FakeVersion(semantic_version="1.0.0"),
                    FakeVersion(semantic_version="2.0.0"),
                ]
            )
        )

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

