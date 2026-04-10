"""Factory for building the Synapse OAuth proxy."""

import logging
import os
from typing import Optional

from cryptography.fernet import Fernet
from fastmcp.server.auth.jwt_issuer import derive_jwt_key
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper

from .config import load_oauth_settings, should_skip_oauth
from .jwt import SynapseJWTVerifier
from .proxy import SessionAwareOAuthProxy

logger = logging.getLogger("synapse_mcp.auth")

OAUTH_ENDPOINTS_BY_ENV = {
    "prod": {
        "jwks_uri": (
            "https://repo-prod.prod.sagebase.org/auth/v1/oauth2/jwks"
        ),
        "issuer": "https://repo-prod.prod.sagebase.org/auth/v1",
        "token_endpoint": (
            "https://repo-prod.prod.sagebase.org/auth/v1/oauth2/token"
        ),
        "authorization_endpoint": "https://signin.synapse.org",
    },
    "staging": {
        "jwks_uri": (
            "https://repo-staging.prod.sagebase.org/auth/v1/oauth2/jwks"
        ),
        "issuer": "https://repo-staging.prod.sagebase.org/auth/v1",
        "token_endpoint": (
            "https://repo-staging.prod.sagebase.org/auth/v1/oauth2/token"
        ),
        "authorization_endpoint": "https://staging-signin.synapse.org",
    },
    "dev": {
        "jwks_uri": (
            "https://repo-dev.dev.sagebase.org/auth/v1/oauth2/jwks"
        ),
        "issuer": "https://repo-dev.dev.sagebase.org/auth/v1",
        "token_endpoint": (
            "https://repo-dev.dev.sagebase.org/auth/v1/oauth2/token"
        ),
        "authorization_endpoint": "https://dev-signin.synapse.org",
    },
}


def create_oauth_proxy(env: Optional[dict[str, str]] = None):
    if should_skip_oauth(env):
        print("SYNAPSE_PAT detected - skipping OAuth configuration")
        return None

    settings = load_oauth_settings(env)
    if not settings:
        print("OAuth configuration missing - running without authentication")
        return None

    # Determine which Synapse environment to use
    env_dict = env if env is not None else os.environ
    synapse_env = env_dict.get("SYNAPSE_ENV", "prod").lower()
    endpoints = OAUTH_ENDPOINTS_BY_ENV.get(
        synapse_env, OAUTH_ENDPOINTS_BY_ENV["prod"]
    )

    logger.info(
        "Configuring OAuth for Synapse environment: %s (issuer: %s)",
        synapse_env,
        endpoints["issuer"],
    )

    jwt_verifier = SynapseJWTVerifier(
        jwks_uri=endpoints["jwks_uri"],
        issuer=endpoints["issuer"],
        audience=settings.client_id,
        algorithm="RS256",
        required_scopes=["openid", "view"],
    )

    client_storage = _create_redis_storage(env_dict, settings.client_secret)

    auth = SessionAwareOAuthProxy(
        upstream_authorization_endpoint=endpoints["authorization_endpoint"],
        upstream_token_endpoint=endpoints["token_endpoint"],
        upstream_client_id=settings.client_id,
        upstream_client_secret=settings.client_secret,
        redirect_path="/oauth/callback",
        token_verifier=jwt_verifier,
        base_url=settings.server_url,
        client_storage=client_storage,
    )

    return auth


def _create_redis_storage(env: dict[str, str], client_secret: str):
    """Create a Redis-backed encrypted storage for OAuth state.

    When REDIS_URL is available, returns a FernetEncryptionWrapper around
    a RedisStore so that upstream tokens, JTI mappings, and refresh tokens
    survive container restarts. Falls back to None (FastMCP's default
    ephemeral DiskStore) when Redis is not configured.
    """
    redis_url = env.get("REDIS_URL")
    if not redis_url:
        logger.info("No REDIS_URL configured — using default ephemeral DiskStore for OAuth state")
        return None

    try:
        from key_value.aio.stores.redis import RedisStore
    except ImportError:
        logger.warning("RedisStore not available — using default ephemeral DiskStore for OAuth state")
        return None

    # Match FastMCP's two-step key derivation:
    # 1) client_secret -> jwt_signing_key (same as OAuthProxy.__init__)
    # 2) jwt_signing_key -> storage_encryption_key
    jwt_signing_key = derive_jwt_key(
        high_entropy_material=client_secret,
        salt="fastmcp-jwt-signing-key",
    )
    encryption_key = derive_jwt_key(
        high_entropy_material=jwt_signing_key.decode(),
        salt="fastmcp-storage-encryption-key",
    )
    redis_store = RedisStore(url=redis_url, default_collection="synapse-mcp-oauth")
    storage = FernetEncryptionWrapper(
        key_value=redis_store,
        fernet=Fernet(key=encryption_key),
    )
    logger.info("Using Redis-backed encrypted storage for OAuth state")
    return storage


__all__ = ["create_oauth_proxy"]
