"""Service layer for Submission operations."""

from typing import Any, Dict, List, Optional

from fastmcp import Context
from synapseclient.models import (
    Submission,
    SubmissionBundle,
    SubmissionStatus,
)

from .tool_service import (
    collect_generator,
    error_boundary,
    serialize_model,
    synapse_client,
)


class SubmissionService:
    """Orchestrates submission read operations."""

    @error_boundary(error_context_keys=("submission_id",))
    def get_submission(
        self, ctx: Context, submission_id: str
    ) -> Dict[str, Any]:
        """Get a single Submission by ID.

        Arguments:
            ctx: The FastMCP request context.
            submission_id: Submission ID string.

        Returns:
            Dict with submission metadata.
        """
        with synapse_client(ctx) as client:
            sub = Submission(id=submission_id).get(
                synapse_client=client,
            )
            return serialize_model(sub)

    @error_boundary(
        error_context_keys=("evaluation_id",),
        wrap_errors=list,
    )
    def list_evaluation_submissions(
        self,
        ctx: Context,
        evaluation_id: str,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List all submissions to an Evaluation.

        Arguments:
            ctx: The FastMCP request context.
            evaluation_id: Evaluation queue ID.
            status: Optional status filter.
            limit: Max results (default 50).

        Returns:
            List of submission dicts.
        """
        with synapse_client(ctx) as client:
            gen = Submission.get_evaluation_submissions(
                evaluation_id=evaluation_id,
                status=status,
                synapse_client=client,
            )
            return [
                serialize_model(s)
                for s in collect_generator(gen, limit)
            ]

    @error_boundary(
        error_context_keys=("evaluation_id",),
        wrap_errors=list,
    )
    def list_my_submissions(
        self,
        ctx: Context,
        evaluation_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List the current user's submissions.

        Arguments:
            ctx: The FastMCP request context.
            evaluation_id: Evaluation queue ID.
            limit: Max results (default 50).

        Returns:
            List of submission dicts.
        """
        with synapse_client(ctx) as client:
            gen = Submission.get_user_submissions(
                evaluation_id=evaluation_id,
                synapse_client=client,
            )
            return [
                serialize_model(s)
                for s in collect_generator(gen, limit)
            ]

    @error_boundary(error_context_keys=("evaluation_id",))
    def get_submission_count(
        self, ctx: Context, evaluation_id: str
    ) -> Dict[str, Any]:
        """Get the count of submissions to an Evaluation.

        Arguments:
            ctx: The FastMCP request context.
            evaluation_id: Evaluation queue ID.

        Returns:
            Dict with the submission count.
        """
        with synapse_client(ctx) as client:
            count = Submission.get_submission_count(
                evaluation_id=evaluation_id,
                synapse_client=client,
            )
            return {
                "evaluation_id": evaluation_id,
                "count": count,
            }

    @error_boundary(error_context_keys=("submission_id",))
    def get_submission_status(
        self, ctx: Context, submission_id: str
    ) -> Dict[str, Any]:
        """Get the status of a Submission.

        Arguments:
            ctx: The FastMCP request context.
            submission_id: Submission ID string.

        Returns:
            Dict with status, score, annotations.
        """
        with synapse_client(ctx) as client:
            status = SubmissionStatus(
                id=submission_id,
            ).get(synapse_client=client)
            return serialize_model(status)

    @error_boundary(
        error_context_keys=("evaluation_id",),
        wrap_errors=list,
    )
    def list_submission_statuses(
        self,
        ctx: Context,
        evaluation_id: str,
        status: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List statuses for all submissions in an Evaluation.

        Arguments:
            ctx: The FastMCP request context.
            evaluation_id: Evaluation queue ID.
            status: Optional status filter.
            limit: Max results (default 10).
            offset: Pagination offset (default 0).

        Returns:
            List of submission status dicts.
        """
        with synapse_client(ctx) as client:
            statuses = (
                SubmissionStatus.get_all_submission_statuses(
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
    def list_evaluation_submission_bundles(
        self,
        ctx: Context,
        evaluation_id: str,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List submission+status bundles for an Evaluation.

        Arguments:
            ctx: The FastMCP request context.
            evaluation_id: Evaluation queue ID.
            status: Optional status filter.
            limit: Max results (default 50).

        Returns:
            List of bundle dicts (submission + status).
        """
        with synapse_client(ctx) as client:
            gen = (
                SubmissionBundle.get_evaluation_submission_bundles(
                    evaluation_id=evaluation_id,
                    status=status,
                    synapse_client=client,
                )
            )
            return [
                serialize_model(b)
                for b in collect_generator(gen, limit)
            ]

    @error_boundary(
        error_context_keys=("evaluation_id",),
        wrap_errors=list,
    )
    def list_my_submission_bundles(
        self,
        ctx: Context,
        evaluation_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List current user's submission bundles.

        Arguments:
            ctx: The FastMCP request context.
            evaluation_id: Evaluation queue ID.
            limit: Max results (default 50).

        Returns:
            List of bundle dicts (submission + status).
        """
        with synapse_client(ctx) as client:
            gen = (
                SubmissionBundle.get_user_submission_bundles(
                    evaluation_id=evaluation_id,
                    synapse_client=client,
                )
            )
            return [
                serialize_model(b)
                for b in collect_generator(gen, limit)
            ]
