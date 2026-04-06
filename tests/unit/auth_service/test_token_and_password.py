from __future__ import annotations

import os
import pytest

from tests.service_loader import load_service_app_module

_PKG = "auth_service_test_app"

@pytest.fixture(scope="module")
def token_module(monkeypatch_module):
    monkeypatch_module.setenv("JWT_SECRET", "test-secret-key-for-ci")
    monkeypatch_module.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch_module.setenv("ACCESS_TOKEN_TTL_MIN", "15")
    monkeypatch_module.setenv("REFRESH_TOKEN_TTL_DAYS", "7")
    return load_service_app_module(
        "auth-service",
        "infrastructure/token_service",
        package_name=_PKG,
        reload_modules=True,
    )

@pytest.fixture(scope="module")
def password_module():
    try:
        mod = load_service_app_module(
            "auth-service",
            "infrastructure/password_hasher",
            package_name=_PKG,
        )
        mod.PasswordHasher().hash("probe")
        return mod
    except (ImportError, ValueError) as exc:
        pytest.skip(f"passlib/bcrypt not available or incompatible: {exc}")

@pytest.fixture(scope="module")
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    yield mp
    mp.undo()

@pytest.mark.unit
class TestIssueTokenPair:
    def test_returns_token_pair_with_all_fields(self, token_module):
        pair = token_module.issue_token_pair(
            user_email="alice@example.com",
            roles=["customer"],
            session_id="sess-1",
        )
        assert pair.access_token
        assert pair.refresh_token
        assert pair.access_expires_at is not None
        assert pair.refresh_expires_at is not None

    def test_access_and_refresh_differ(self, token_module):
        pair = token_module.issue_token_pair(
            user_email="bob@example.com",
            roles=["handyman"],
            session_id="sess-2",
        )
        assert pair.access_token != pair.refresh_token

    def test_refresh_expires_after_access(self, token_module):
        pair = token_module.issue_token_pair(
            user_email="carol@example.com",
            roles=["admin"],
            session_id="sess-3",
        )
        assert pair.refresh_expires_at > pair.access_expires_at

@pytest.mark.unit
class TestDecodeToken:
    def test_roundtrip_access(self, token_module):
        pair = token_module.issue_token_pair(
            user_email="dave@example.com",
            roles=["customer"],
            session_id="sess-4",
        )
        payload = token_module.decode_token(pair.access_token)
        assert payload["sub"] == "dave@example.com"
        assert payload["roles"] == ["customer"]
        assert payload["sid"] == "sess-4"

    def test_roundtrip_refresh(self, token_module):
        pair = token_module.issue_token_pair(
            user_email="eve@example.com",
            roles=["handyman"],
            session_id="sess-5",
        )
        payload = token_module.decode_token(pair.refresh_token)
        assert payload["sub"] == "eve@example.com"
        assert payload["typ"] == "refresh"

    def test_invalid_token_raises(self, token_module):
        with pytest.raises(token_module.JWTError):
            token_module.decode_token("this.is.invalid")

@pytest.mark.unit
class TestHashToken:
    def test_deterministic(self, token_module):
        h1 = token_module.hash_token("my-token")
        h2 = token_module.hash_token("my-token")
        assert h1 == h2

    def test_different_inputs_differ(self, token_module):
        assert token_module.hash_token("a") != token_module.hash_token("b")

    def test_returns_hex_string(self, token_module):
        result = token_module.hash_token("test")
        assert isinstance(result, str)
        assert len(result) == 64  # sha256 hex

@pytest.mark.unit
class TestGenerateOpaqueToken:
    def test_returns_string(self, token_module):
        assert isinstance(token_module.generate_opaque_token(), str)

    def test_unique(self, token_module):
        tokens = {token_module.generate_opaque_token() for _ in range(20)}
        assert len(tokens) == 20

@pytest.mark.unit
class TestPasswordHasher:
    def test_hash_and_verify(self, password_module):
        hasher = password_module.PasswordHasher()
        hashed = hasher.hash("s3cret!")
        assert hasher.verify("s3cret!", hashed) is True

    def test_wrong_password_fails(self, password_module):
        hasher = password_module.PasswordHasher()
        hashed = hasher.hash("correct")
        assert hasher.verify("wrong", hashed) is False

    def test_different_hashes_for_same_password(self, password_module):
        hasher = password_module.PasswordHasher()
        h1 = hasher.hash("same")
        h2 = hasher.hash("same")
        assert h1 != h2  # bcrypt uses random salt

    def test_singleton_instance(self, password_module):
        assert password_module.password_hasher is not None
        hashed = password_module.password_hasher.hash("test")
        assert password_module.password_hasher.verify("test", hashed)