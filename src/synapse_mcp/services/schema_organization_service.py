"""Service layer for JSON Schema Organization operations."""

import json
from typing import Any, Dict, List, Optional

from fastmcp import Context
from synapseclient.models import JSONSchema, SchemaOrganization

from .tool_service import (
    error_boundary,
    serialize_model,
    synapse_client,
)


async def _post_one_page(
    client,
    uri: str,
    body: Dict[str, Any],
    next_page_token: Optional[str],
) -> Dict[str, Any]:
    """Issue a single POST page against a token-paginated Synapse endpoint.

    The Synapse list endpoints (``/schema/list``,
    ``/schema/version/list``, ``/form/data/list``) follow the
    ``ListRequest``/``ListResponse`` shape: the request body carries an
    optional ``nextPageToken``; the response returns ``{"page": [...],
    "nextPageToken": "..."}``. This helper sends one POST and hands the
    raw response back so callers can decide whether to ask for the next
    page. We do **not** auto-iterate — surfacing the token is the only
    way the MCP caller can paginate, since the API has no
    ``limit``/``offset``.
    """
    if next_page_token is not None:
        body = {**body, "nextPageToken": next_page_token}
    return await client.rest_post_async(uri=uri, body=json.dumps(body))


class SchemaOrganizationService:
    """Orchestrates JSON schema organization read operations."""

    @staticmethod
    @error_boundary(error_context_keys=("organization_name",))
    async def get_schema_organization(
        ctx: Context,
        organization_name: str,
    ) -> Dict[str, Any]:
        """Get a Schema Organization by name.

        Arguments:
            ctx: The FastMCP request context.
            organization_name: Organization name string.

        Returns:
            Dict with organization metadata.
        """
        async with synapse_client(ctx) as client:
            org = await SchemaOrganization(
                name=organization_name,
            ).get_async(synapse_client=client)
            return serialize_model(org)

    @staticmethod
    @error_boundary(error_context_keys=("organization_name",))
    async def get_schema_organization_acl(
        ctx: Context, organization_name: str
    ) -> Dict[str, Any]:
        """Get the ACL for a Schema Organization.

        Arguments:
            ctx: The FastMCP request context.
            organization_name: Organization name string.

        Returns:
            Dict with ACL information.
        """
        async with synapse_client(ctx) as client:
            org = SchemaOrganization(name=organization_name)
            # get_async populates org.id, which get_acl_async needs for the API call.
            await org.get_async(synapse_client=client)
            acl = await org.get_acl_async(synapse_client=client)
            return serialize_model(acl)

    @staticmethod
    @error_boundary(
        error_context_keys=("organization_name",),
    )
    async def list_json_schemas(
        ctx: Context,
        organization_name: str,
        next_page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List schemas in an organization (one page at a time).

        Synapse's ``/schema/list`` endpoint paginates with a
        ``nextPageToken``, not ``limit``/``offset``. This call returns
        a single page; the caller passes the returned ``next_page_token``
        back in to fetch the next page. ``next_page_token`` is ``None``
        when the last page has been served.

        Arguments:
            ctx: The FastMCP request context.
            organization_name: Organization name string.
            next_page_token: Token from the previous page's response.
                Omit (or pass ``None``) to start from the first page.

        Returns:
            Dict with ``results`` (list of schema info dicts),
            ``next_page_token`` (string or None), and the originating
            ``organization_name``.
        """
        async with synapse_client(ctx) as client:
            response = await _post_one_page(
                client,
                "/schema/list",
                {"organizationName": organization_name},
                next_page_token,
            )
            results: List[Dict[str, Any]] = [
                serialize_model(item) for item in response.get("page", [])
            ]
            return {
                "organization_name": organization_name,
                "results": results,
                "next_page_token": response.get("nextPageToken"),
            }

    @staticmethod
    @error_boundary(error_context_keys=("organization_name", "schema_name"))
    async def get_json_schema(
        ctx: Context,
        organization_name: str,
        schema_name: str,
    ) -> Dict[str, Any]:
        """Get metadata for a specific JSON Schema.

        Arguments:
            ctx: The FastMCP request context.
            organization_name: Organization name string.
            schema_name: Schema name string.

        Returns:
            Dict with schema metadata.
        """
        async with synapse_client(ctx) as client:
            schema = await JSONSchema(
                organization_name=organization_name,
                name=schema_name,
            ).get_async(synapse_client=client)
            return serialize_model(schema)

    @staticmethod
    @error_boundary(error_context_keys=("organization_name", "schema_name"))
    async def get_json_schema_body(
        ctx: Context,
        organization_name: str,
        schema_name: str,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get the actual JSON body of a schema.

        Arguments:
            ctx: The FastMCP request context.
            organization_name: Organization name string.
            schema_name: Schema name string.
            version: Optional semantic version.

        Returns:
            Dict containing the raw JSON schema document.
        """
        async with synapse_client(ctx) as client:
            schema = JSONSchema(
                organization_name=organization_name,
                name=schema_name,
            )
            body = await schema.get_body_async(
                version=version,
                synapse_client=client,
            )
            return serialize_model(body)

    @staticmethod
    @error_boundary(
        error_context_keys=("organization_name", "schema_name"),
    )
    async def list_json_schema_versions(
        ctx: Context,
        organization_name: str,
        schema_name: str,
        next_page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List versions of a JSON Schema (one page at a time).

        Same token-pagination contract as ``list_json_schemas``.

        Arguments:
            ctx: The FastMCP request context.
            organization_name: Organization name string.
            schema_name: Schema name string.
            next_page_token: Token from the previous page; ``None`` to
                start from the first page.

        Returns:
            Dict with ``results`` (list of version info dicts),
            ``next_page_token`` (string or None), and identifying
            ``organization_name`` / ``schema_name``.
        """
        async with synapse_client(ctx) as client:
            response = await _post_one_page(
                client,
                "/schema/version/list",
                {
                    "organizationName": organization_name,
                    "schemaName": schema_name,
                },
                next_page_token,
            )
            results: List[Dict[str, Any]] = [
                serialize_model(item) for item in response.get("page", [])
            ]
            return {
                "organization_name": organization_name,
                "schema_name": schema_name,
                "results": results,
                "next_page_token": response.get("nextPageToken"),
            }
