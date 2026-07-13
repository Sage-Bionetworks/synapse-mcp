"""Service layer for Evaluation (challenge queue) operations."""

from typing import Any, Dict, List, Optional

from fastmcp import Context
from synapseclient.models import Evaluation

from ..tool_types import UNSET, EvaluationAccessType
from .tool_service import error_boundary, serialize_model, synapse_client


class EvaluationService:
    """Orchestrates evaluation read operations."""

    @staticmethod
    @error_boundary(
        error_context_keys=("evaluation_id", "evaluation_name")
    )
    async def get_evaluation(
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
        if evaluation_id is None and evaluation_name is None:
            return {
                "error": (
                    "Either evaluation_id or "
                    "evaluation_name is required"
                )
            }
        async with synapse_client(ctx) as client:
            if evaluation_id is not None:
                ev = await Evaluation(id=evaluation_id).get_async(
                    synapse_client=client,
                )
            else:
                ev = await Evaluation(name=evaluation_name).get_async(
                    synapse_client=client,
                )
            return serialize_model(ev)

    @staticmethod
    @error_boundary(wrap_errors=True)
    async def list_evaluations(
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
        async with synapse_client(ctx) as client:
            if project_id is not None:
                evals = await Evaluation.get_evaluations_by_project_async(
                    project_id=project_id,
                    access_type=access_type,
                    active_only=active_only,
                    evaluation_ids=evaluation_ids,
                    offset=offset,
                    limit=limit,
                    synapse_client=client,
                )
            elif available_only:
                evals = await Evaluation.get_available_evaluations_async(
                    active_only=active_only,
                    evaluation_ids=evaluation_ids,
                    offset=offset,
                    limit=limit,
                    synapse_client=client,
                )
            else:
                evals = await Evaluation.get_all_evaluations_async(
                    access_type=access_type,
                    active_only=active_only,
                    evaluation_ids=evaluation_ids,
                    offset=offset,
                    limit=limit,
                    synapse_client=client,
                )
            return [serialize_model(e) for e in evals]

    @staticmethod
    @error_boundary(error_context_keys=("evaluation_id",))
    async def get_evaluation_acl(
        ctx: Context, evaluation_id: str
    ) -> Dict[str, Any]:
        """Get the ACL for an Evaluation queue.

        Arguments:
            ctx: The FastMCP request context.
            evaluation_id: Evaluation queue ID.

        Returns:
            Dict with ACL information.
        """
        async with synapse_client(ctx) as client:
            ev = Evaluation(id=evaluation_id)
            acl = await ev.get_acl_async(synapse_client=client)
            return {
                "evaluation_id": evaluation_id,
                "acl": serialize_model(acl),
            }

    @staticmethod
    @error_boundary(error_context_keys=("evaluation_id",))
    async def get_evaluation_permissions(
        ctx: Context, evaluation_id: str
    ) -> Dict[str, Any]:
        """Get current user's permissions on an Evaluation.

        Arguments:
            ctx: The FastMCP request context.
            evaluation_id: Evaluation queue ID.

        Returns:
            Dict with permission flags.
        """
        async with synapse_client(ctx) as client:
            ev = Evaluation(id=evaluation_id)
            perms = await ev.get_permissions_async(
                synapse_client=client,
            )
            return {
                "evaluation_id": evaluation_id,
                "permissions": serialize_model(perms),
            }

    @staticmethod
    @error_boundary(error_context_keys=("content_source",))
    async def create_evaluation(
        ctx: Context,
        name: str,
        content_source: str,
        description: str,
        submission_instructions_message: str,
        submission_receipt_message: str,
    ) -> Dict[str, Any]:
        """Create a new Evaluation queue on a Synapse project.

        The Synapse API requires all of name, description, content_source,
        submission_instructions_message, and submission_receipt_message to
        create an evaluation; each is passed straight through.

        Arguments:
            ctx: The FastMCP request context.
            name: Evaluation queue name.
            content_source: Synapse project ID that owns the queue
                (e.g. syn123456).
            description: Description of the queue.
            submission_instructions_message: Instructions shown to
                submitters.
            submission_receipt_message: Message shown after a submission
                is received.

        Returns:
            Dict with the created evaluation metadata.
        """
        async with synapse_client(ctx) as client:
            ev = Evaluation(
                name=name,
                content_source=content_source,
                description=description,
                submission_instructions_message=(
                    submission_instructions_message
                ),
                submission_receipt_message=submission_receipt_message,
            )
            stored = await ev.store_async(synapse_client=client)
            return serialize_model(stored)

    @staticmethod
    @error_boundary(error_context_keys=("evaluation_id",))
    async def update_evaluation(
        ctx: Context,
        evaluation_id: str,
        name: Optional[str] = UNSET,
        description: Optional[str] = UNSET,
        submission_instructions_message: Optional[str] = UNSET,
    ) -> Dict[str, Any]:
        """Update an existing Evaluation queue's metadata.

        Each field is only touched when supplied. Note the Synapse API
        requires name, description, and submitter instructions on an
        evaluation, so clearing one to null is rejected server-side.

        Arguments:
            ctx: The FastMCP request context.
            evaluation_id: Evaluation queue ID (e.g. "9600001").
            name: New name.
            description: New description.
            submission_instructions_message: New submitter instructions.

        Returns:
            Dict with the updated evaluation metadata.
        """
        for field, value in (
            ("name", name),
            ("description", description),
            ("submission_instructions_message", submission_instructions_message),
        ):
            if value is not UNSET and value is None:
                return {
                    "error": (
                        f"'{field}' is required and cannot be cleared to "
                        "null; supply a non-null value or omit it to leave "
                        "it unchanged."
                    )
                }
        async with synapse_client(ctx) as client:
            ev = await Evaluation(id=evaluation_id).get_async(
                synapse_client=client,
            )
            if name is not UNSET:
                ev.name = name
            if description is not UNSET:
                ev.description = description
            if submission_instructions_message is not UNSET:
                ev.submission_instructions_message = (
                    submission_instructions_message
                )
            stored = await ev.store_async(synapse_client=client)
            return serialize_model(stored)

    @staticmethod
    @error_boundary(error_context_keys=("evaluation_id",))
    async def delete_evaluation(
        ctx: Context, evaluation_id: str
    ) -> Dict[str, Any]:
        """Delete an Evaluation queue by ID.

        Arguments:
            ctx: The FastMCP request context.
            evaluation_id: Evaluation queue ID (e.g. "9600001").

        Returns:
            Dict confirming the deletion.
        """
        async with synapse_client(ctx) as client:
            await Evaluation(id=evaluation_id).delete_async(
                synapse_client=client,
            )
            return {"evaluation_id": evaluation_id, "deleted": True}

    @staticmethod
    @error_boundary(error_context_keys=("evaluation_id", "principal_id"))
    async def update_evaluation_acl(
        ctx: Context,
        evaluation_id: str,
        principal_id: int,
        access_type: List[EvaluationAccessType],
    ) -> Dict[str, Any]:
        """Grant or update a principal's access on an Evaluation queue.

        Arguments:
            ctx: The FastMCP request context.
            evaluation_id: Evaluation queue ID (e.g. "9600001").
            principal_id: User or team ID to grant access to.
            access_type: Permission strings (e.g. ["READ", "SUBMIT"]).

        Returns:
            Dict with the updated ACL.
        """
        async with synapse_client(ctx) as client:
            ev = Evaluation(id=evaluation_id)
            result = await ev.update_acl_async(
                principal_id=principal_id,
                access_type=access_type,
                synapse_client=client,
            )
            return {
                "evaluation_id": evaluation_id,
                "principal_id": principal_id,
                "acl": serialize_model(result),
            }
