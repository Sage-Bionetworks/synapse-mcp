"""FastMCP OAuth proxy extensions for Synapse."""

import logging
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from fastmcp.server.auth import OAuthProxy

logger = logging.getLogger("synapse_mcp.oauth")


class SessionAwareOAuthProxy(OAuthProxy):
    """OAuth proxy that delegates client storage to FastMCP's built-in client_storage."""

    async def register_client(self, client_info):
        # Ensure grant_types includes refresh_token — many MCP clients
        # (including Claude Code) only send authorization_code.  The MCP
        # spec and FastMCP require both, so we normalise before validation.
        if client_info.grant_types:
            grants = list(client_info.grant_types)
            if "authorization_code" in grants and "refresh_token" not in grants:
                grants.append("refresh_token")
                client_info.grant_types = grants
                logger.debug("Normalised grant_types to include refresh_token")

        logger.debug(
            "register_client called with: id=%s, redirect_uris=%s, grants=%s",
            client_info.client_id,
            client_info.redirect_uris,
            client_info.grant_types,
        )
        await super().register_client(client_info)

    async def _handle_idp_callback(self, request, *args, **kwargs):
        result = await super()._handle_idp_callback(request, *args, **kwargs)

        if result and hasattr(result, "headers"):
            location = result.headers.get("location")
            if location:
                parsed = urlparse(location)
                query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
                filtered_pairs = [
                    (key, value)
                    for key, value in query_pairs
                    if not (
                        key == "state"
                        and (
                            value is None
                            or value == ""
                            or (isinstance(value, str) and value.lower() == "none")
                        )
                    )
                ]

                if len(filtered_pairs) != len(query_pairs):
                    new_query = urlencode(filtered_pairs, doseq=True)
                    new_location = urlunparse(parsed._replace(query=new_query))
                    result.headers["location"] = new_location
                    logger.debug("Removed empty state parameter from callback redirect")

        return result


__all__ = ["SessionAwareOAuthProxy"]
