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

    @error_boundary(error_context_keys=("owner_id",))
    def get_wiki_page(
        self,
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
        with synapse_client(ctx) as client:
            if wiki_id is None:
                # SDK requires id or title — find root page
                # from the wiki header tree.
                headers = list(WikiHeader.get(
                    owner_id=owner_id,
                    synapse_client=client,
                ))
                root = None
                for h in headers:
                    pid = getattr(h, "parent_id", None)
                    if pid is None:
                        root = h
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
            page = WikiPage(
                owner_id=owner_id,
                id=wiki_id,
            ).get(synapse_client=client)
            return serialize_model(page)

    @error_boundary(
        error_context_keys=("owner_id",),
        wrap_errors=list,
    )
    def get_wiki_headers(
        self,
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
        with synapse_client(ctx) as client:
            headers = WikiHeader.get(
                owner_id=owner_id,
                offset=offset,
                limit=limit,
                synapse_client=client,
            )
            return [
                serialize_model(h) for h in headers
            ]

    @error_boundary(
        error_context_keys=("owner_id",),
        wrap_errors=list,
    )
    def get_wiki_history(
        self,
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
        with synapse_client(ctx) as client:
            snapshots = WikiHistorySnapshot.get(
                owner_id=owner_id,
                id=wiki_id,
                offset=offset,
                limit=limit,
                synapse_client=client,
            )
            return [
                serialize_model(s) for s in snapshots
            ]

    @error_boundary(error_context_keys=("owner_id",))
    def get_wiki_order_hint(
        self, ctx: Context, owner_id: str
    ) -> Dict[str, Any]:
        """Get the display ordering of wiki sub-pages.

        Arguments:
            ctx: The FastMCP request context.
            owner_id: Synapse ID of the wiki owner.

        Returns:
            Dict with owner_id, id_list (page ordering),
            and etag.
        """
        with synapse_client(ctx) as client:
            hint = WikiOrderHint(
                owner_id=owner_id,
            ).get(synapse_client=client)
            return serialize_model(hint)
