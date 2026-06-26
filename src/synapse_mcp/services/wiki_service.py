"""Service layer for Wiki operations."""

from typing import Any, Dict, List, Optional

from fastmcp import Context
from synapseclient.models import (
    WikiHeader,
    WikiHistorySnapshot,
    WikiOrderHint,
    WikiPage,
)
from synapseclient.core.exceptions import SynapseHTTPError

from .tool_service import error_boundary, serialize_model, synapse_client


class WikiService:
    """Orchestrates wiki read operations."""

    @staticmethod
    @error_boundary(error_context_keys=("owner_id",))
    async def get_wiki_page(
        ctx: Context,
        owner_id: str,
        wiki_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a wiki page's content and metadata.
        If wiki_id is omitted, returns the root wiki page for the given owner_id.
        If wiki_id is provided, returns the wiki page with the given id.

        Arguments:
            ctx: The FastMCP request context.
            owner_id: Synapse ID of the entity that owns
                the wiki (e.g. ``"syn123"``).
            wiki_id: Optional wiki page ID. If omitted,
                returns the root wiki page.

        Returns:
            Dict with page id, title, parent_id, owner_id, wiki_version,
            markdown_file_handle_id, attachment_file_handle_ids, and timestamps.
            Or if owner_id is not provided or the root wiki page is not found,
            returns a dict with an error key and message.
        """
        if not owner_id:
            return {
                "error": ("The owner_id is required to get a wiki page"),
            }
        async with synapse_client(ctx) as client:
            if wiki_id is None:
                # SDK requires id or title — find the root page from the
                # wiki header tree. Limit the page size to keep root
                # discovery cheap; we only need the parent_id == None
                # entry, which lives in the first page.
                root = None
                try:
                    async for header in WikiHeader.get_async(
                        owner_id=owner_id,
                        offset=0,
                        limit=50,
                        synapse_client=client,
                    ):
                        if getattr(header, "parent_id", None) is None:
                            root = header
                            break
                except SynapseHTTPError as exc:
                    if getattr(exc.response, "status_code", None) == 404:
                        return {
                            "error": f"No root wiki page found for {owner_id}",
                            "owner_id": owner_id,
                        }
                    raise
                wiki_id = root.id
            page = await WikiPage(
                owner_id=owner_id,
                id=wiki_id,
            ).get_async(synapse_client=client)
            return serialize_model(page)

    @staticmethod
    @error_boundary(
        error_context_keys=("owner_id",),
        wrap_errors=True,
    )
    async def get_wiki_headers(
        ctx: Context,
        owner_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get the wiki header tree (table of contents) for an entity.

        Arguments:
            ctx: The FastMCP request context.
            owner_id: Synapse ID of the entity that owns
                the wiki.
            offset: Pagination offset (default 0).
            limit: Maximum headers to return (default 50).

        Returns:
            List of dicts with id, title, and parent_id
            for each wiki page in the hierarchy.
            Or if owner_id is not provided or the wiki header tree is not found,
            returns a dict with an error key and message.
        """
        if not owner_id:
            return {
                "error": ("The owner_id is required to get the wiki header tree"),
            }
        async with synapse_client(ctx) as client:
            # ``WikiHeader.get_async`` forwards limit/offset into the
            # paginated REST call. The async generator continues across
            # pages until exhausted, so we cap manually at ``limit``
            # items to keep response sizes bounded; callers paginate
            # further by passing a larger ``offset``.
            results: List[Dict[str, Any]] = []
            async for header in WikiHeader.get_async(
                owner_id=owner_id,
                offset=offset,
                limit=limit,
                synapse_client=client,
            ):
                if len(results) >= limit:
                    break
                results.append(serialize_model(header))
            if not results:
                return {
                    "error": ("No wiki headers found for the given owner_id"),
                }
            return results

    @staticmethod
    @error_boundary(
        error_context_keys=("owner_id", "wiki_id"),
        wrap_errors=True,
    )
    async def get_wiki_history(
        ctx: Context,
        owner_id: str,
        wiki_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get the revision history of a wiki page.

        Arguments:
            ctx: The FastMCP request context.
            owner_id: Synapse ID of the wiki owner.
            wiki_id: The wiki page ID to get the history for.
            offset: Pagination offset (default 0).
            limit: Max snapshots to return (default 50).

        Returns:
            List of dicts with version, modified_on
            and modified_by for each snapshot in the history.
            Or if owner_id and wiki_id are not provided, returns a dict with an error key and message.
        """
        if not owner_id or not wiki_id:
            return {
                "error": (
                    "Both the owner_id and wiki_id are required to get the wiki history"
                ),
            }
        async with synapse_client(ctx) as client:
            results: List[Dict[str, Any]] = []
            async for snapshot in WikiHistorySnapshot.get_async(
                owner_id=owner_id,
                id=wiki_id,
                offset=offset,
                limit=limit,
                synapse_client=client,
            ):
                if len(results) >= limit:
                    break
                results.append(serialize_model(snapshot))
            return results

    @staticmethod
    @error_boundary(error_context_keys=("owner_id",))
    async def get_wiki_order_hint(ctx: Context, owner_id: str) -> Dict[str, Any]:
        """Get the display ordering of wiki sub-pages.
        The wiki order hint is empty by default.
        This function returns the current wiki order hint for the given owner_id if set

        Arguments:
            ctx: The FastMCP request context.
            owner_id: The Synapse ID of the wiki owner.

        Returns:
            Dict with owner_id, owner_object_type, id_list (page ordering),
            and etag.
            Or if the wiki order hint is not set, returns an error.
        """
        if not owner_id:
            return {
                "error": ("The owner_id is required to get the wiki order hint"),
            }
        async with synapse_client(ctx) as client:
            hint = await WikiOrderHint(
                owner_id=owner_id,
            ).get_async(synapse_client=client)
            if not hint.id_list:
                return {
                    "error": ("The wiki order hint is not set for the given owner_id."),
                }
            return serialize_model(hint)
