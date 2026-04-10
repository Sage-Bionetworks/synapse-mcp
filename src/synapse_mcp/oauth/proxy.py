"""FastMCP OAuth proxy extensions for Synapse."""

import logging
import os
from typing import Any, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from fastmcp.server.auth import OAuthProxy
from fastmcp.server.auth.oauth_proxy import ProxyDCRClient
from mcp.server.auth.provider import OAuthClientInformationFull
from pydantic import AnyUrl, TypeAdapter

from .client_registry import (
    ClientRegistration,
    create_client_registry,
    load_static_registrations,
)

logger = logging.getLogger("synapse_mcp.oauth")


class SessionAwareOAuthProxy(OAuthProxy):
    """OAuth proxy with persistent client registry backed by Redis/file."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._client_registry = create_client_registry(os.environ)
        logger.debug(
            "SessionAwareOAuthProxy initialized with client registry %s",
            type(self._client_registry).__name__,
        )

    def _registration_to_proxy_client(self, record: ClientRegistration) -> ProxyDCRClient:
        """Build a ProxyDCRClient from a persisted ClientRegistration."""
        default_grants = ["authorization_code", "refresh_token"]
        adapter = TypeAdapter(List[AnyUrl])
        redirect_source = record.redirect_uris if record.redirect_uris else [
            "http://127.0.0.1"]
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

        Checks FastMCP's in-process ``_client_store`` first (covers
        clients registered during *this* process lifetime), then falls
        back to the persistent registry (Redis / file) so that clients
        survive container restarts without bulk-loading into memory.
        """
        client = await super().get_client(client_id)
        if client is not None:
            return client

        # Persistent registry lookup (Redis hget or file read)
        registration = self._client_registry.load_one(client_id)
        if registration is None:
            # Also check static registrations
            for static in load_static_registrations():
                if static.client_id == client_id:
                    registration = static
                    break
        if registration is None:
            return None

        proxy_client = self._registration_to_proxy_client(registration)

        # Cache into _client_store so subsequent lookups in this
        # container's lifetime (e.g. /consent, /token in the same
        # auth flow) hit the local store instead of Redis.
        try:
            await self._client_store.put(key=client_id, value=proxy_client)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Failed to cache client %s in local store: %s", client_id, exc)

        logger.info("Resolved client %s from persistent registry", client_id)
        return proxy_client

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

        logger.debug("register_client called with: id=%s, redirect_uris=%s, grants=%s",
                     client_info.client_id, client_info.redirect_uris, client_info.grant_types)
        await super().register_client(client_info)

        try:
            registration = ClientRegistration(
                client_id=client_info.client_id,
                client_secret=_extract_secret(client_info.client_secret),
                redirect_uris=[str(uri)
                               for uri in (client_info.redirect_uris or [])],
                grant_types=list(client_info.grant_types or [
                                 "authorization_code", "refresh_token"]),
            )
            self._client_registry.save(registration)
            logger.debug("Persisted OAuth client %s with redirect_uris=%s and grants=%s",
                         client_info.client_id, registration.redirect_uris, registration.grant_types)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Unable to persist OAuth client %s: %s",
                           client_info.client_id, exc)

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
                    logger.debug(
                        "Removed empty state parameter from callback redirect")

        return result


def _extract_secret(secret: Any) -> Optional[str]:
    if secret is None:
        return None
    try:
        return secret.get_secret_value()  # type: ignore[attr-defined]
    except AttributeError:
        return secret  # type: ignore[return-value]


__all__ = ["SessionAwareOAuthProxy"]
