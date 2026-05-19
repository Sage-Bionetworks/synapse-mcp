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
    async def test_given_organization_when_listed_then_returns_one_page_with_token(
        self, mock_get_client: AsyncMock
    ):
        # GIVEN /schema/list returns a page plus a continuation token.
        client = MagicMock()
        client.rest_post_async = AsyncMock(
            return_value={
                "page": [
                    {"organizationName": "sage.example", "schemaName": "SchemaA"},
                    {"organizationName": "sage.example", "schemaName": "SchemaB"},
                ],
                "nextPageToken": "tok-2",
            }
        )
        mock_get_client.return_value = client

        # WHEN we list the first page
        result = await SchemaOrganizationService.list_json_schemas(
            MagicMock(), organization_name="sage.example"
        )

        # THEN we get a one-page response shape with the continuation
        # token surfaced for the caller to ask for the next page.
        assert result["organization_name"] == "sage.example"
        assert result["next_page_token"] == "tok-2"
        assert [r["schemaName"] for r in result["results"]] == [
            "SchemaA",
            "SchemaB",
        ]
        # Body should NOT include nextPageToken on the first call.
        body = client.rest_post_async.call_args.kwargs["body"]
        import json as _json
        assert _json.loads(body) == {"organizationName": "sage.example"}

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_token_when_listed_then_forwards_in_body(
        self, mock_get_client: AsyncMock
    ):
        # GIVEN a caller paginating with a previous page's token
        client = MagicMock()
        client.rest_post_async = AsyncMock(
            return_value={"page": [], "nextPageToken": None}
        )
        mock_get_client.return_value = client

        # WHEN we ask for the next page
        result = await SchemaOrganizationService.list_json_schemas(
            MagicMock(),
            organization_name="sage.example",
            next_page_token="tok-2",
        )

        # THEN the token rides in the request body and the response
        # surfaces a null next_page_token (signalling end of pagination).
        body = client.rest_post_async.call_args.kwargs["body"]
        import json as _json
        assert _json.loads(body) == {
            "organizationName": "sage.example",
            "nextPageToken": "tok-2",
        }
        assert result["next_page_token"] is None
        assert result["results"] == []

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_when_called_then_returns_error_dict(
        self, mock_get_client: AsyncMock
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError("expired")

        # WHEN we list schemas
        result = await SchemaOrganizationService.list_json_schemas(
            MagicMock(), organization_name="sage.example"
        )

        # THEN the auth error is returned as a single error dict
        # (no list-wrapping — the response shape is a dict, not a list).
        assert isinstance(result, dict)
        assert "Authentication required" in result["error"]
        assert result["organization_name"] == "sage.example"


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
    async def test_given_schema_when_list_versions_then_returns_one_page(
        self, mock_get_client: AsyncMock
    ):
        # GIVEN /schema/version/list returns a page plus a token
        client = MagicMock()
        client.rest_post_async = AsyncMock(
            return_value={
                "page": [
                    {"semanticVersion": "1.0.0"},
                    {"semanticVersion": "2.0.0"},
                ],
                "nextPageToken": "v-2",
            }
        )
        mock_get_client.return_value = client

        # WHEN we list versions
        result = await SchemaOrganizationService.list_json_schema_versions(
            MagicMock(),
            organization_name="sage.example",
            schema_name="ExampleSchema",
        )

        # THEN the page surfaces with the continuation token
        assert result["organization_name"] == "sage.example"
        assert result["schema_name"] == "ExampleSchema"
        assert result["next_page_token"] == "v-2"
        assert [v["semanticVersion"] for v in result["results"]] == [
            "1.0.0",
            "2.0.0",
        ]
        # First call should not include nextPageToken in the request body.
        import json as _json
        body = _json.loads(client.rest_post_async.call_args.kwargs["body"])
        assert body == {
            "organizationName": "sage.example",
            "schemaName": "ExampleSchema",
        }

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_token_when_listed_then_forwards_in_body(
        self, mock_get_client: AsyncMock
    ):
        client = MagicMock()
        client.rest_post_async = AsyncMock(
            return_value={"page": [], "nextPageToken": None}
        )
        mock_get_client.return_value = client

        await SchemaOrganizationService.list_json_schema_versions(
            MagicMock(),
            organization_name="sage.example",
            schema_name="ExampleSchema",
            next_page_token="v-2",
        )

        import json as _json
        body = _json.loads(client.rest_post_async.call_args.kwargs["body"])
        assert body == {
            "organizationName": "sage.example",
            "schemaName": "ExampleSchema",
            "nextPageToken": "v-2",
        }

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_when_called_then_returns_error_dict(
        self, mock_get_client: AsyncMock
    ):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = await SchemaOrganizationService.list_json_schema_versions(
            MagicMock(),
            organization_name="sage.example",
            schema_name="ExampleSchema",
        )

        assert isinstance(result, dict)
        assert "Authentication required" in result["error"]
        assert result["organization_name"] == "sage.example"
        assert result["schema_name"] == "ExampleSchema"

