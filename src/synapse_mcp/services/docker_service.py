"""Service layer for DockerRepository operations."""

from typing import Any, Dict

from fastmcp import Context
from synapseclient.models import DockerRepository

from .tool_service import error_boundary, serialize_model, synapse_client


class DockerService:
    """Orchestrates Docker repository read operations."""

    @error_boundary(error_context_keys=("entity_id",))
    async def get_docker_repository(
        self, ctx: Context, entity_id: str
    ) -> Dict[str, Any]:
        """Get a DockerRepository entity by ID.

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID of a DockerRepository.

        Returns:
            Dict with DockerRepository metadata.
        """
        async with synapse_client(ctx) as client:
            repo = await DockerRepository(id=entity_id).get_async(
                synapse_client=client,
            )
            return serialize_model(repo)
