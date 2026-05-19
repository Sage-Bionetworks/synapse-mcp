"""Service layer for Wiki operations."""

from typing import Any, Dict, List, Optional

from fastmcp import Context
from synapseclient.models import (
    WikiHeader,
    WikiHistorySnapshot,
    WikiOrderHint,
    WikiPage,
)

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

        Arguments:
            ctx: The FastMCP request context.
            owner_id: Synapse ID of the entity that owns
                the wiki (e.g. ``"syn123"``).
            wiki_id: Optional wiki page ID. If omitted,
                returns the root wiki page.

        Returns:
            Dict with page id, title, markdown content,
            owner_id, parent_wiki_id, and timestamps.
        """
        async with synapse_client(ctx) as client:
            if wiki_id is None:
                # SDK requires id or title — find the root page from the
                # wiki header tree. Limit the page size to keep root
                # discovery cheap; we only need the parent_id == None
                # entry, which lives in the first page.
                root = None
                async for header in WikiHeader.get_async(
                    owner_id=owner_id,
                    offset=0,
                    limit=50,
                    synapse_client=client,
                ):
                    if getattr(header, "parent_id", None) is None:
                        root = header
                        break
                if root is None:
                    return {
                        "error": (
                            f"No root wiki page found for"
                            f" {owner_id}"
                        ),
                        "owner_id": owner_id,
                    }
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
        """Get the wiki table of contents for an entity.

        Arguments:
            ctx: The FastMCP request context.
            owner_id: Synapse ID of the entity that owns
                the wiki.
            offset: Pagination offset (default 0).
            limit: Maximum headers to return (default 50).

        Returns:
            List of dicts with id, title, and parent_id
            for each wiki page in the hierarchy.
        """
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
            return results

    @staticmethod
    @error_boundary(
        error_context_keys=("owner_id",),
        wrap_errors=True,
    )
    async def get_wiki_history(
        ctx: Context,
        owner_id: str,
        wiki_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get revision history of a wiki page.

        Arguments:
            ctx: The FastMCP request context.
            owner_id: Synapse ID of the wiki owner.
            wiki_id: Wiki page ID.
            offset: Pagination offset (default 0).
            limit: Max snapshots to return (default 50).

        Returns:
            List of dicts with version, modified_on,
            and modified_by for each revision.
        """
        async with synapse_client(ctx) as client:
            results: List[Dict[str, Any]] = []
            async for snap in WikiHistorySnapshot.get_async(
                owner_id=owner_id,
                id=wiki_id,
                offset=offset,
                limit=limit,
                synapse_client=client,
            ):
                if len(results) >= limit:
                    break
                results.append(serialize_model(snap))
            return results

    @staticmethod
    @error_boundary(error_context_keys=("owner_id",))
    async def get_wiki_order_hint(
        ctx: Context, owner_id: str
    ) -> Dict[str, Any]:
        """Get the display ordering of wiki sub-pages.

        Arguments:
            ctx: The FastMCP request context.
            owner_id: Synapse ID of the wiki owner.

        Returns:
            Dict with owner_id, id_list (page ordering),
            and etag.
        """
        async with synapse_client(ctx) as client:
            hint = await WikiOrderHint(
                owner_id=owner_id,
            ).get_async(synapse_client=client)
            return serialize_model(hint)
