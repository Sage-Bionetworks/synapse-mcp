"""Service layer for Evaluation (challenge queue) operations."""

from typing import Any, Dict, List, Optional

from fastmcp import Context
from synapseclient.models import Evaluation

from .tool_service import error_boundary, serialize_model, synapse_client


class EvaluationService:
    """Orchestrates evaluation read operations."""

    @error_boundary(
        error_context_keys=("evaluation_id", "evaluation_name")
    )
    def get_evaluation(
        self,
        ctx: Context,
        evaluation_id: Optional[str] = None,
        evaluation_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get an Evaluation by ID or name.

        Arguments:
            ctx: The FastMCP request context.
            evaluation_id: Numeric evaluation queue ID.
            evaluation_name: Evaluation name string.

        Returns:
            Dict with evaluation metadata.
        """
        with synapse_client(ctx) as client:
            if evaluation_id is not None:
                ev = Evaluation(id=evaluation_id).get(
                    synapse_client=client,
                )
            elif evaluation_name is not None:
                ev = Evaluation(name=evaluation_name).get(
                    synapse_client=client,
                )
            else:
                return {
                    "error": (
                        "Either evaluation_id or "
                        "evaluation_name is required"
                    )
                }
            return serialize_model(ev)

    @error_boundary(wrap_errors=list)
    def list_evaluations(
        self,
        ctx: Context,
        project_id: Optional[str] = None,
        access_type: Optional[str] = None,
        active_only: Optional[bool] = None,
        available_only: bool = False,
        evaluation_ids: Optional[List[str]] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """List evaluations with optional filters.

        Arguments:
            ctx: The FastMCP request context.
            project_id: Filter by project ID.
            access_type: Filter by access type.
            active_only: Only return active evaluations.
            available_only: Only evaluations the user
                can submit to.
            evaluation_ids: Specific evaluation IDs.
            offset: Pagination offset (default 0).
            limit: Max results (default 20).

        Returns:
            List of evaluation dicts.
        """
        with synapse_client(ctx) as client:
            if project_id is not None:
                evals = Evaluation.get_evaluations_by_project(
                    project_id=project_id,
                    access_type=access_type,
                    active_only=active_only,
                    evaluation_ids=evaluation_ids,
                    offset=offset,
                    limit=limit,
                    synapse_client=client,
                )
            elif available_only:
                evals = Evaluation.get_available_evaluations(
                    active_only=active_only,
                    evaluation_ids=evaluation_ids,
                    offset=offset,
                    limit=limit,
                    synapse_client=client,
                )
            else:
                evals = Evaluation.get_all_evaluations(
                    access_type=access_type,
                    active_only=active_only,
                    evaluation_ids=evaluation_ids,
                    offset=offset,
                    limit=limit,
                    synapse_client=client,
                )
            return [serialize_model(e) for e in evals]

    @error_boundary(error_context_keys=("evaluation_id",))
    def get_evaluation_acl(
        self, ctx: Context, evaluation_id: str
    ) -> Dict[str, Any]:
        """Get the ACL for an Evaluation queue.

        Arguments:
            ctx: The FastMCP request context.
            evaluation_id: Evaluation queue ID.

        Returns:
            Dict with ACL information.
        """
        with synapse_client(ctx) as client:
            ev = Evaluation(id=evaluation_id)
            acl = ev.get_acl(synapse_client=client)
            return {
                "evaluation_id": evaluation_id,
                "acl": serialize_model(acl),
            }

    @error_boundary(error_context_keys=("evaluation_id",))
    def get_evaluation_permissions(
        self, ctx: Context, evaluation_id: str
    ) -> Dict[str, Any]:
        """Get current user's permissions on an Evaluation.

        Arguments:
            ctx: The FastMCP request context.
            evaluation_id: Evaluation queue ID.

        Returns:
            Dict with permission flags.
        """
        with synapse_client(ctx) as client:
            ev = Evaluation(id=evaluation_id)
            perms = ev.get_permissions(
                synapse_client=client,
            )
            return {
                "evaluation_id": evaluation_id,
                "permissions": serialize_model(perms),
            }
