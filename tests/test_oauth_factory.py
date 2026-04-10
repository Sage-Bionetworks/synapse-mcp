"""Tests for the OAuth factory's Redis storage creation."""

import pytest

from synapse_mcp.oauth.factory import _create_redis_storage


def test_create_redis_storage_returns_none_without_redis_url():
    """Without REDIS_URL, factory returns None (falls back to DiskStore)."""
    result = _create_redis_storage({}, "test-secret")
    assert result is None


def test_create_redis_storage_returns_none_with_empty_redis_url():
    result = _create_redis_storage({"REDIS_URL": ""}, "test-secret")
    assert result is None


def test_create_redis_storage_returns_encrypted_wrapper(monkeypatch):
    """With REDIS_URL, factory returns a FernetEncryptionWrapper around RedisStore."""
    from key_value.aio.wrappers.encryption import FernetEncryptionWrapper

    storage = _create_redis_storage(
        {"REDIS_URL": "redis://localhost:6379"},
        "test-secret-with-enough-entropy",
    )
    assert storage is not None
    assert isinstance(storage, FernetEncryptionWrapper)
