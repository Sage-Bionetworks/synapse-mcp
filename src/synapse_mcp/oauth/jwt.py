"""Synapse-specific JWT verification for FastMCP."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from fastmcp.server.auth.auth import AccessToken
from jwt import PyJWKClient, decode
from jwt.exceptions import PyJWTError

logger = logging.getLogger("synapse_mcp.oauth")


class SynapseJWTVerifier:
    """JWT verifier that adapts Synapse tokens to FastMCP's expectations."""

    def __init__(
        self,
        jwks_uri: str,
        issuer: str,
        audience: str,
        algorithm: str = "RS256",
        required_scopes: Optional[List[str]] = None,
    ) -> None:
        self.issuer = issuer
        self.audience = audience
        self.algorithm = algorithm
        self.required_scopes = required_scopes or []
        self.jwks_client = PyJWKClient(uri=jwks_uri)
        self._executor = ThreadPoolExecutor(max_workers=2)

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(self._executor, self._verify_token_sync, token)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Error in async Synapse JWT verification: %s", exc)
            return None

    def _verify_token_sync(self, token: str) -> Optional[AccessToken]:
        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)

            decoded = decode(
                jwt=token,
                key=signing_key.key,
                algorithms=[self.algorithm],
                audience=self.audience,
                issuer=self.issuer,
                options={"verify_aud": True},
            )

            scopes = self._extract_synapse_scopes(decoded)
            if not self._validate_required_scopes(scopes):
                logger.warning("Required scopes validation failed")
                return None

            return self._create_fastmcp_access_token(decoded, scopes, token)

        except PyJWTError as exc:
            logger.error("JWT verification FAILED: %s (type: %s)",
                         exc, type(exc).__name__)
            return None

    def _extract_synapse_scopes(self, decoded: Dict[str, Any]) -> List[str]:
        if "access" in decoded and "scope" in decoded["access"]:
            scopes = decoded["access"]["scope"]
            logger.debug(
                "Found scopes in Synapse nested structure: %s", scopes)
        elif "scope" in decoded:
            scope_str = decoded["scope"]
            scopes = scope_str.split(" ") if isinstance(
                scope_str, str) else scope_str
            logger.debug("Found scopes in standard location: %s", scopes)
        else:
            scopes = []
        return scopes if isinstance(scopes, list) else []

    def _validate_required_scopes(self, token_scopes: List[str]) -> bool:
        if not self.required_scopes:
            return True
        token_scope_set = set(token_scopes)
        required_scope_set = set(self.required_scopes)
        missing = required_scope_set - token_scope_set
        if missing:
            logger.warning("Missing required scopes: %s", missing)
            return False
        return True

    def _create_fastmcp_access_token(
        self, decoded: Dict[str, Any], scopes: List[str], token: str
    ) -> AccessToken:
        aud = decoded.get("aud", "")
        if isinstance(aud, list):
            client_id = aud[0] if aud else ""
        else:
            client_id = aud or ""
        access_token = AccessToken(
            token=token,
            client_id=client_id,
            scopes=scopes,
            expires_at=decoded.get("exp"),
            claims=decoded,
        )
        logger.debug(
            "Created FastMCP access token for subject: %s", decoded.get("sub"))
        return access_token

    def __del__(self) -> None:  # pragma: no cover - cleanup
        if hasattr(self, "_executor"):
            self._executor.shutdown(wait=False)


__all__ = ["SynapseJWTVerifier"]
