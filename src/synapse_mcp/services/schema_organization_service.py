"""Service layer for JSON Schema Organization operations."""

from typing import Any, Dict, List, Optional

from fastmcp import Context
from synapseclient.models import JSONSchema, SchemaOrganization

from .tool_service import error_boundary, serialize_model, synapse_client


class SchemaOrganizationService:
    """Orchestrates JSON schema organization read operations."""

    @error_boundary(
        error_context_keys=(
            "organization_name",
            "organization_id",
        )
    )
    def get_schema_organization(
        self,
        ctx: Context,
        organization_name: Optional[str] = None,
        organization_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get a Schema Organization by name or ID.

        Arguments:
            ctx: The FastMCP request context.
            organization_name: Organization name string.
            organization_id: Numeric organization ID.

        Returns:
            Dict with organization metadata.
        """
        with synapse_client(ctx) as client:
            if organization_name is not None:
                org = SchemaOrganization(
                    name=organization_name,
                ).get(synapse_client=client)
            elif organization_id is not None:
                org = SchemaOrganization(
                    id=organization_id,
                ).get(synapse_client=client)
            else:
                return {
                    "error": (
                        "Either organization_name or "
                        "organization_id is required"
                    )
                }
            return serialize_model(org)

    @error_boundary(
        error_context_keys=("organization_name",)
    )
    def get_schema_organization_acl(
        self, ctx: Context, organization_name: str
    ) -> Dict[str, Any]:
        """Get the ACL for a Schema Organization.

        Arguments:
            ctx: The FastMCP request context.
            organization_name: Organization name string.

        Returns:
            Dict with ACL information.
        """
        with synapse_client(ctx) as client:
            org = SchemaOrganization(
                name=organization_name,
            )
            acl = org.get_acl(synapse_client=client)
            return {
                "organization_name": organization_name,
                "acl": serialize_model(acl),
            }

    @error_boundary(
        error_context_keys=("organization_name",),
        wrap_errors=list,
    )
    def list_json_schemas(
        self, ctx: Context, organization_name: str
    ) -> List[Dict[str, Any]]:
        """List all schemas in an organization.

        Arguments:
            ctx: The FastMCP request context.
            organization_name: Organization name string.

        Returns:
            List of JSON schema metadata dicts.
        """
        with synapse_client(ctx) as client:
            org = SchemaOrganization(
                name=organization_name,
            )
            schemas = org.get_json_schemas(
                synapse_client=client,
            )
            return [serialize_model(s) for s in schemas]

    @error_boundary(
        error_context_keys=(
            "organization_name",
            "schema_name",
        )
    )
    def get_json_schema(
        self,
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
        with synapse_client(ctx) as client:
            schema = JSONSchema(
                organization_name=organization_name,
                name=schema_name,
            ).get(synapse_client=client)
            return serialize_model(schema)

    @error_boundary(
        error_context_keys=(
            "organization_name",
            "schema_name",
        )
    )
    def get_json_schema_body(
        self,
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
        with synapse_client(ctx) as client:
            schema = JSONSchema(
                organization_name=organization_name,
                name=schema_name,
            )
            body = schema.get_body(
                version=version,
                synapse_client=client,
            )
            return serialize_model(body)

    @error_boundary(
        error_context_keys=(
            "organization_name",
            "schema_name",
        ),
        wrap_errors=list,
    )
    def list_json_schema_versions(
        self,
        ctx: Context,
        organization_name: str,
        schema_name: str,
    ) -> List[Dict[str, Any]]:
        """List all versions of a JSON Schema.

        Arguments:
            ctx: The FastMCP request context.
            organization_name: Organization name string.
            schema_name: Schema name string.

        Returns:
            List of version info dicts.
        """
        with synapse_client(ctx) as client:
            schema = JSONSchema(
                organization_name=organization_name,
                name=schema_name,
            )
            versions = schema.get_versions(
                synapse_client=client,
            )
            return [serialize_model(v) for v in versions]
