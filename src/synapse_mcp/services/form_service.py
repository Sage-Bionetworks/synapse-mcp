"""Service layer for Form operations."""

import json
from typing import Any, Dict, List, Optional

from fastmcp import Context

from .tool_service import error_boundary, serialize_model, synapse_client


class FormService:
    """Orchestrates form read operations."""

    @staticmethod
    @error_boundary(
        error_context_keys=("group_id", "as_reviewer"),
    )
    async def list_form_data(
        ctx: Context,
        group_id: str,
        filter_by_state: Optional[List[str]] = None,
        as_reviewer: bool = False,
        next_page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List form submissions for a FormGroup (one page at a time).

        Synapse's ``/form/data/list[/reviewer]`` endpoints paginate via
        ``nextPageToken`` in the request and response bodies — there is
        no ``limit``/``offset``. This call returns a single page; pass
        the returned ``next_page_token`` back in to fetch the next.

        Arguments:
            ctx: The FastMCP request context.
            group_id: FormGroup ID string.
            filter_by_state: Optional list of submission states to
                filter by. Valid values:
                ``waiting_for_submission``,
                ``submitted_waiting_for_review``, ``accepted``,
                ``rejected``. ``waiting_for_submission`` is not allowed
                when ``as_reviewer=True``.
            as_reviewer: If True, hits the reviewer endpoint
                (``/form/data/list/reviewer``) which returns FormData
                for the entire group; requires
                ``READ_PRIVATE_SUBMISSION``. If False (default), lists
                only the caller's own submissions.
            next_page_token: Token from the previous page; ``None`` to
                start from the first page.

        Returns:
            Dict with ``results`` (list of FormData dicts),
            ``next_page_token`` (string or None), and the originating
            ``group_id``.
        """
        uri = (
            "/form/data/list/reviewer"
            if as_reviewer
            else "/form/data/list"
        )
        body: Dict[str, Any] = {
            "groupId": group_id,
            "filterByState": filter_by_state or [],
        }
        if next_page_token is not None:
            body["nextPageToken"] = next_page_token
        async with synapse_client(ctx) as client:
            response = await client.rest_post_async(
                uri=uri, body=json.dumps(body)
            )
            results: List[Dict[str, Any]] = [
                serialize_model(item) for item in response.get("page", [])
            ]
            return {
                "group_id": group_id,
                "results": results,
                "next_page_token": response.get("nextPageToken"),
            }
