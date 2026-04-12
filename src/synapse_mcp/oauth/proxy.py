"""FastMCP OAuth proxy extensions for Synapse."""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from fastmcp.server.auth import OAuthProxy
from fastmcp.server.auth.oauth_proxy.models import ProxyDCRClient
from mcp.server.auth.provider import OAuthClientInformationFull
from pydantic import AnyUrl, TypeAdapter

logger = logging.getLogger("synapse_mcp.oauth")


@dataclass
class _StaticClient:
    """Minimal representation of a statically configured OAuth client."""

    client_id: str
    client_secret: Optional[str]
    redirect_uris: list[str]
    grant_types: list[str]


def _load_static_clients() -> list[_StaticClient]:
    """Load statically configured clients from environment or file."""
    raw = os.environ.get("SYNAPSE_MCP_STATIC_CLIENTS")
    path = os.environ.get("SYNAPSE_MCP_STATIC_CLIENTS_PATH")

    data: Optional[str] = None
    if path:
        try:
            data = Path(path).expanduser().read_text()
        except Exception as exc:
            logger.warning("Failed to read static client file %s: %s", path, exc)
    elif raw:
        data = raw

    if not data:
        return []

    try:
        payload = json.loads(data)
    except json.JSONDecodeError as exc:
        logger.warning("Invalid JSON in static client configuration: %s", exc)
        return []

    if not isinstance(payload, list):
        logger.warning("Static client configuration must be a list of objects")
        return []

    clients: list[_StaticClient] = []
    for item in payload:
        try:
            clients.append(
                _StaticClient(
                    client_id=item["client_id"],
                    client_secret=item.get("client_secret"),
                    redirect_uris=list(item.get("redirect_uris", [])),
                    grant_types=list(item.get("grant_types", [])),
                )
            )
        except KeyError as exc:
            logger.warning("Skipping malformed static client entry missing %s", exc)
    return clients


class SessionAwareOAuthProxy(OAuthProxy):
    """OAuth proxy with static client fallback on top of FastMCP's built-in client_storage."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._static_clients = _load_static_clients()

    def _static_to_proxy_client(self, record: _StaticClient) -> ProxyDCRClient:
        """Build a ProxyDCRClient from a static client config."""
        default_grants = ["authorization_code", "refresh_token"]
        adapter = TypeAdapter(List[AnyUrl])
        redirect_source = record.redirect_uris if record.redirect_uris else ["http://127.0.0.1"]
        redirect_uris = adapter.validate_python(redirect_source)
        return ProxyDCRClient(
            client_id=record.client_id,
            client_secret=record.client_secret,
            redirect_uris=redirect_uris,
            grant_types=record.grant_types or default_grants,
            scope=self._default_scope_str,
            token_endpoint_auth_method="none",
            allowed_redirect_uri_patterns=self._allowed_client_redirect_uris,
        )

    async def get_client(self, client_id: str) -> Optional[OAuthClientInformationFull]:
        """Look up a registered client.

        Checks FastMCP's client_storage first (persists clients registered via
        DCR across container restarts), then falls back to static registrations.
        """
        client = await super().get_client(client_id)
        if client is not None:
            return client

        for static in self._static_clients:
            if static.client_id == client_id:
                logger.info("Resolved client %s from static registrations", client_id)
                return self._static_to_proxy_client(static)

        return None

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
