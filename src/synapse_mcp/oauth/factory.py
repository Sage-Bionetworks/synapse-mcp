"""Factory for building the Synapse OAuth proxy."""

import logging
import os
from typing import Optional

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
        "authorization_endpoint": "https://signin.synapse.org",
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

    auth = SessionAwareOAuthProxy(
        upstream_authorization_endpoint=endpoints["authorization_endpoint"],
        upstream_token_endpoint=endpoints["token_endpoint"],
        upstream_client_id=settings.client_id,
        upstream_client_secret=settings.client_secret,
        redirect_path="/oauth/callback",
        token_verifier=jwt_verifier,
        base_url=settings.server_url,
    )

    return auth


__all__ = ["create_oauth_proxy"]
