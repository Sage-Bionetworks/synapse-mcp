"""Service layer for Form operations."""

from typing import Any, Dict, List, Optional

from fastmcp import Context
from synapseclient.models import FormGroup

from .tool_service import error_boundary, serialize_model, synapse_client


class FormService:
    """Orchestrates form read operations."""

    @error_boundary(
        error_context_keys=("group_id",),
        wrap_errors=list,
    )
    def list_form_data(
        self,
        ctx: Context,
        group_id: str,
        filter_by_state: Optional[List[str]] = None,
        as_reviewer: bool = False,
    ) -> List[Dict[str, Any]]:
        """List form submissions for a FormGroup.

        Arguments:
            ctx: The FastMCP request context.
            group_id: FormGroup ID string.
            filter_by_state: Optional list of states
                to filter by (e.g. SUBMITTED, ACCEPTED).
            as_reviewer: If True, list as reviewer.

        Returns:
            List of form data submission dicts.
        """
        with synapse_client(ctx) as client:
            group = FormGroup(group_id=group_id)
            submissions = group.list(
                filter_by_state=filter_by_state,
                as_reviewer=as_reviewer,
                synapse_client=client,
            )
            return [
                serialize_model(s) for s in submissions
            ]
