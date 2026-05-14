"""Service layer for JSON Schema Organization operations."""

from typing import Any, Optional

from fastmcp import Context
from synapseclient.models import JSONSchema, SchemaOrganization

from .tool_service import (
    collect_async_generator,
    error_boundary,
    serialize_model,
    synapse_client,
)


class SchemaOrganizationService:
    """Orchestrates JSON schema organization read operations."""

    @error_boundary(error_context_keys=("organization_name",))
    async def get_schema_organization(
        self,
        ctx: Context,
        organization_name: str,
    ) -> dict[str, Any]:
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

    @error_boundary(error_context_keys=("organization_name",))
    async def get_schema_organization_acl(
        self, ctx: Context, organization_name: str
    ) -> dict[str, Any]:
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

    @error_boundary(
        error_context_keys=("organization_name", "limit"),
        wrap_errors=list,
    )
    async def list_json_schemas(
        self,
        ctx: Context,
        organization_name: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List all schemas in an organization.

        Arguments:
            ctx: The FastMCP request context.
            organization_name: Organization name string.
            limit: Maximum number of schemas to return.

        Returns:
            List of JSON schema metadata dicts.
        """
        async with synapse_client(ctx) as client:
            org = SchemaOrganization(
                name=organization_name,
            )
            schemas = await collect_async_generator(
                org.get_json_schemas_async(synapse_client=client),
                limit,
            )
            return [serialize_model(schema) for schema in schemas]

    @error_boundary(error_context_keys=("organization_name", "schema_name"))
    async def get_json_schema(
        self,
        ctx: Context,
        organization_name: str,
        schema_name: str,
    ) -> dict[str, Any]:
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

    @error_boundary(error_context_keys=("organization_name", "schema_name"))
    async def get_json_schema_body(
        self,
        ctx: Context,
        organization_name: str,
        schema_name: str,
        version: Optional[str] = None,
    ) -> dict[str, Any]:
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

    @error_boundary(
        error_context_keys=("organization_name", "schema_name", "limit"),
        wrap_errors=list,
    )
    async def list_json_schema_versions(
        self,
        ctx: Context,
        organization_name: str,
        schema_name: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List all versions of a JSON Schema.

        Arguments:
            ctx: The FastMCP request context.
            organization_name: Organization name string.
            schema_name: Schema name string.
            limit: Maximum number of versions to return.

        Returns:
            List of version info dicts.
        """
        async with synapse_client(ctx) as client:
            schema = JSONSchema(
                organization_name=organization_name,
                name=schema_name,
            )
            versions = await collect_async_generator(
                schema.get_versions_async(synapse_client=client),
                limit,
            )
            return [serialize_model(v) for v in versions]
