"""Service layer for Submission operations."""

from typing import Any, Dict, List, Optional

from fastmcp import Context
from synapseclient.models import (
    Submission,
    SubmissionBundle,
    SubmissionStatus,
)

from .tool_service import (
    collect_async_generator,
    error_boundary,
    serialize_model,
    synapse_client,
)


class SubmissionService:
    """Orchestrates submission read operations."""

    @error_boundary(error_context_keys=("submission_id",))
    async def get_submission(
        self, ctx: Context, submission_id: str
    ) -> Dict[str, Any]:
        """Get a single Submission by ID."""
        async with synapse_client(ctx) as client:
            sub = await Submission(id=submission_id).get_async(
                synapse_client=client,
            )
            return serialize_model(sub)

    @error_boundary(
        error_context_keys=("evaluation_id",),
        wrap_errors=list,
    )
    async def list_evaluation_submissions(
        self,
        ctx: Context,
        evaluation_id: str,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List all submissions to an Evaluation."""
        async with synapse_client(ctx) as client:
            gen = Submission.get_evaluation_submissions_async(
                evaluation_id=evaluation_id,
                status=status,
                synapse_client=client,
            )
            items = await collect_async_generator(gen, limit)
            return [serialize_model(s) for s in items]

    @error_boundary(
        error_context_keys=("evaluation_id",),
        wrap_errors=list,
    )
    async def list_my_submissions(
        self,
        ctx: Context,
        evaluation_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List the current user's submissions."""
        async with synapse_client(ctx) as client:
            gen = Submission.get_user_submissions_async(
                evaluation_id=evaluation_id,
                synapse_client=client,
            )
            items = await collect_async_generator(gen, limit)
            return [serialize_model(s) for s in items]

    @error_boundary(error_context_keys=("evaluation_id",))
    async def get_submission_count(
        self, ctx: Context, evaluation_id: str
    ) -> Dict[str, Any]:
        """Get the count of submissions to an Evaluation."""
        async with synapse_client(ctx) as client:
            count = await Submission.get_submission_count_async(
                evaluation_id=evaluation_id,
                synapse_client=client,
            )
            return {
                "evaluation_id": evaluation_id,
                "count": count,
            }

    @error_boundary(error_context_keys=("submission_id",))
    async def get_submission_status(
        self, ctx: Context, submission_id: str
    ) -> Dict[str, Any]:
        """Get the status of a Submission."""
        async with synapse_client(ctx) as client:
            status = await SubmissionStatus(
                id=submission_id,
            ).get_async(synapse_client=client)
            return serialize_model(status)

    @error_boundary(
        error_context_keys=("evaluation_id",),
        wrap_errors=list,
    )
    async def list_submission_statuses(
        self,
        ctx: Context,
        evaluation_id: str,
        status: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List statuses for all submissions in an Evaluation."""
        async with synapse_client(ctx) as client:
            statuses = await (
                SubmissionStatus.get_all_submission_statuses_async(
                    evaluation_id=evaluation_id,
                    status=status,
                    limit=limit,
                    offset=offset,
                    synapse_client=client,
                )
            )
            return [serialize_model(s) for s in statuses]

    @error_boundary(
        error_context_keys=("evaluation_id",),
        wrap_errors=list,
    )
    async def list_evaluation_submission_bundles(
        self,
        ctx: Context,
        evaluation_id: str,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List submission+status bundles for an Evaluation."""
        async with synapse_client(ctx) as client:
            gen = (
                SubmissionBundle.get_evaluation_submission_bundles_async(
                    evaluation_id=evaluation_id,
                    status=status,
                    synapse_client=client,
                )
            )
            items = await collect_async_generator(gen, limit)
            return [serialize_model(b) for b in items]

    @error_boundary(
        error_context_keys=("evaluation_id",),
        wrap_errors=list,
    )
    async def list_my_submission_bundles(
        self,
        ctx: Context,
        evaluation_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List current user's submission bundles."""
        async with synapse_client(ctx) as client:
            gen = (
                SubmissionBundle.get_user_submission_bundles_async(
                    evaluation_id=evaluation_id,
                    synapse_client=client,
                )
            )
            items = await collect_async_generator(gen, limit)
            return [serialize_model(b) for b in items]
