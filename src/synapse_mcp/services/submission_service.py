"""Service layer for Submission operations."""

from typing import Any, Dict, List, Optional

from fastmcp import Context
from synapseclient.api.api_client import rest_get_paginated_async
from synapseclient.models import (
    Submission,
    SubmissionBundle,
    SubmissionStatus,
)

from .tool_service import error_boundary, serialize_model, synapse_client


def _submission_uri(
    evaluation_id: str,
    *,
    user_scoped: bool,
    bundles: bool,
    status: Optional[str] = None,
) -> str:
    """Build a paginated submission URI for ``rest_get_paginated_async``.

    Mirrors the URIs used by ``synapseclient.api.evaluation_services``:
    - ``/evaluation/{id}/submission/all`` — every submission to a queue
    - ``/evaluation/{id}/submission`` — caller's own submissions only
    - ``/evaluation/{id}/submission/bundle/all`` — all bundles
    - ``/evaluation/{id}/submission/bundle`` — caller's own bundles
    """
    base = f"/evaluation/{evaluation_id}/submission"
    if bundles:
        suffix = "/bundle/all" if not user_scoped else "/bundle"
    else:
        suffix = "/all" if not user_scoped else ""
    uri = base + suffix
    if status:
        uri = f"{uri}?status={status}"
    return uri


class SubmissionService:
    """Orchestrates submission read operations."""

    @staticmethod
    @error_boundary(error_context_keys=("submission_id",))
    async def get_submission(
        ctx: Context, submission_id: str
    ) -> Dict[str, Any]:
        """Get a single Submission by ID."""
        async with synapse_client(ctx) as client:
            sub = await Submission(id=submission_id).get_async(
                synapse_client=client,
            )
            return serialize_model(sub)

    @staticmethod
    @error_boundary(
        error_context_keys=("evaluation_id",),
        wrap_errors=True,
    )
    async def list_evaluation_submissions(
        ctx: Context,
        evaluation_id: str,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List submissions to an Evaluation queue (any user).

        Pagination reaches the wire via ``rest_get_paginated_async``
        against ``/evaluation/{id}/submission/all`` so ``limit`` and
        ``offset`` query params actually skip records server-side.
        Each REST dict is rehydrated via ``Submission.fill_from_dict``
        so the response matches the high-level
        ``Submission.get_evaluation_submissions_async`` shape.
        """
        if limit < 0 or offset < 0:
            raise ValueError("limit and offset must be >= 0")
        if limit == 0:
            return []
        uri = _submission_uri(
            evaluation_id,
            user_scoped=False,
            bundles=False,
            status=status,
        )
        async with synapse_client(ctx) as client:
            results: List[Dict[str, Any]] = []
            async for raw in rest_get_paginated_async(
                uri=uri,
                limit=limit,
                offset=offset,
                synapse_client=client,
            ):
                if len(results) >= limit:
                    break
                sub = Submission().fill_from_dict(
                    synapse_submission=raw,
                )
                results.append(serialize_model(sub))
            return results

    @staticmethod
    @error_boundary(
        error_context_keys=("evaluation_id",),
        wrap_errors=True,
    )
    async def list_my_submissions(
        ctx: Context,
        evaluation_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List the caller's own submissions to an Evaluation."""
        if limit < 0 or offset < 0:
            raise ValueError("limit and offset must be >= 0")
        if limit == 0:
            return []
        uri = _submission_uri(
            evaluation_id, user_scoped=True, bundles=False
        )
        async with synapse_client(ctx) as client:
            results: List[Dict[str, Any]] = []
            async for raw in rest_get_paginated_async(
                uri=uri,
                limit=limit,
                offset=offset,
                synapse_client=client,
            ):
                if len(results) >= limit:
                    break
                sub = Submission().fill_from_dict(
                    synapse_submission=raw,
                )
                results.append(serialize_model(sub))
            return results

    @staticmethod
    @error_boundary(error_context_keys=("evaluation_id",))
    async def get_submission_count(
        ctx: Context, evaluation_id: str
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

    @staticmethod
    @error_boundary(error_context_keys=("submission_id",))
    async def get_submission_status(
        ctx: Context, submission_id: str
    ) -> Dict[str, Any]:
        """Get the status of a Submission."""
        async with synapse_client(ctx) as client:
            status = await SubmissionStatus(
                id=submission_id,
            ).get_async(synapse_client=client)
            return serialize_model(status)

    @staticmethod
    @error_boundary(
        error_context_keys=("evaluation_id",),
        wrap_errors=True,
    )
    async def list_submission_statuses(
        ctx: Context,
        evaluation_id: str,
        status: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List statuses for all submissions in an Evaluation.

        ``SubmissionStatus.get_all_submission_statuses_async`` already
        accepts ``limit``/``offset`` and forwards them, so we pass
        them straight through.
        """
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

    @staticmethod
    @error_boundary(
        error_context_keys=("evaluation_id",),
        wrap_errors=True,
    )
    async def list_evaluation_submission_bundles(
        ctx: Context,
        evaluation_id: str,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List submission+status bundles for an Evaluation."""
        if limit < 0 or offset < 0:
            raise ValueError("limit and offset must be >= 0")
        if limit == 0:
            return []
        uri = _submission_uri(
            evaluation_id,
            user_scoped=False,
            bundles=True,
            status=status,
        )
        async with synapse_client(ctx) as client:
            results: List[Dict[str, Any]] = []
            async for raw in rest_get_paginated_async(
                uri=uri,
                limit=limit,
                offset=offset,
                synapse_client=client,
            ):
                if len(results) >= limit:
                    break
                bundle = SubmissionBundle().fill_from_dict(
                    synapse_submission_bundle=raw,
                )
                results.append(serialize_model(bundle))
            return results

    @staticmethod
    @error_boundary(
        error_context_keys=("evaluation_id",),
        wrap_errors=True,
    )
    async def list_my_submission_bundles(
        ctx: Context,
        evaluation_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List the caller's submission bundles for an Evaluation."""
        if limit < 0 or offset < 0:
            raise ValueError("limit and offset must be >= 0")
        if limit == 0:
            return []
        uri = _submission_uri(
            evaluation_id, user_scoped=True, bundles=True
        )
        async with synapse_client(ctx) as client:
            results: List[Dict[str, Any]] = []
            async for raw in rest_get_paginated_async(
                uri=uri,
                limit=limit,
                offset=offset,
                synapse_client=client,
            ):
                if len(results) >= limit:
                    break
                bundle = SubmissionBundle().fill_from_dict(
                    synapse_submission_bundle=raw,
                )
                results.append(serialize_model(bundle))
            return results

    @staticmethod
    @error_boundary(error_context_keys=("evaluation_id", "entity_id"))
    async def submit_to_evaluation(
        ctx: Context,
        evaluation_id: str,
        entity_id: str,
        name: Optional[str] = None,
        submitter_alias: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit an existing Synapse entity to an Evaluation queue.

        The submission references an entity that already exists in Synapse
        (e.g. a File or Docker entity) by ID — no file is uploaded here.

        Arguments:
            ctx: The FastMCP request context.
            evaluation_id: Target evaluation queue ID (e.g. "9600001").
            entity_id: Synapse ID of the entity to submit (e.g. syn123456).
            name: Optional submission name.
            submitter_alias: Optional alias shown on the leaderboard.

        Returns:
            Dict with the created submission metadata.
        """
        async with synapse_client(ctx) as client:
            submission = Submission(
                evaluation_id=evaluation_id,
                entity_id=entity_id,
                name=name,
                submitter_alias=submitter_alias,
            )
            stored = await submission.store_async(synapse_client=client)
            return serialize_model(stored)

    @staticmethod
    @error_boundary(error_context_keys=("submission_id",))
    async def update_submission_status(
        ctx: Context,
        submission_id: str,
        status: Optional[str] = None,
        annotations: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update the scoring status of a Synapse submission.

        Arguments:
            ctx: The FastMCP request context.
            submission_id: Submission ID (e.g. "9722233").
            status: New status (e.g. SCORED, INVALID, ACCEPTED, REJECTED).
            annotations: Optional submission-status annotations to set.

        Returns:
            Dict with the updated submission status.
        """
        async with synapse_client(ctx) as client:
            sub_status = await SubmissionStatus(
                id=submission_id
            ).get_async(synapse_client=client)
            if status is not None:
                sub_status.status = status
            if annotations is not None:
                sub_status.submission_annotations = annotations
            stored = await sub_status.store_async(synapse_client=client)
            return serialize_model(stored)
