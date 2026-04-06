from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

def _make_request():
    request = MagicMock()
    request.state = MagicMock()
    return request

def _make_valid_token(security_module):
    from jose import jwt

    return jwt.encode(
        {"sub": "user@example.com", "roles": ["user"]},
        security_module.JWT_SECRET,
        algorithm=security_module.JWT_ALGORITHM,
    )

def _make_creds(token: str):
    creds = MagicMock()
    creds.scheme = "Bearer"
    creds.credentials = token
    return creds


@pytest.mark.unit
class TestGetCurrentUserSSE:
    def test_authenticates_via_query_param(self, security_module):
        request = _make_request()
        token = _make_valid_token(security_module)

        result = security_module.get_current_user_sse(
            request=request,
            access_token=token,
            creds=None,
        )

        assert result["sub"] == "user@example.com"
        assert result["roles"] == ["user"]
        assert request.state.user_sub == "user@example.com"

    def test_authenticates_via_bearer_header(self, security_module):
        request = _make_request()
        token = _make_valid_token(security_module)
        creds = _make_creds(token)

        result = security_module.get_current_user_sse(
            request=request,
            access_token=None,
            creds=creds,
        )

        assert result["sub"] == "user@example.com"
        assert request.state.user_sub == "user@example.com"

    def test_query_param_takes_priority_over_header(self, security_module):
        from jose import jwt as jose_jwt

        request = _make_request()

        query_token = jose_jwt.encode(
            {"sub": "query-user@example.com", "roles": ["user"]},
            security_module.JWT_SECRET,
            algorithm=security_module.JWT_ALGORITHM,
        )
        header_token = jose_jwt.encode(
            {"sub": "header-user@example.com", "roles": ["user"]},
            security_module.JWT_SECRET,
            algorithm=security_module.JWT_ALGORITHM,
        )

        result = security_module.get_current_user_sse(
            request=request,
            access_token=query_token,
            creds=_make_creds(header_token),
        )

        assert result["sub"] == "query-user@example.com"

    def test_rejects_missing_token(self, security_module):
        request = _make_request()

        with pytest.raises(HTTPException) as exc_info:
            security_module.get_current_user_sse(
                request=request,
                access_token=None,
                creds=None,
            )

        assert exc_info.value.status_code == 401
        assert "Missing access token" in exc_info.value.detail

    def test_rejects_invalid_token(self, security_module):
        request = _make_request()

        with pytest.raises(HTTPException) as exc_info:
            security_module.get_current_user_sse(
                request=request,
                access_token="this-is-not-a-valid-jwt",
                creds=None,
            )

        assert exc_info.value.status_code == 401
        assert "Invalid or expired" in exc_info.value.detail

    def test_rejects_expired_token(self, security_module):
        from jose import jwt as jose_jwt
        import time

        request = _make_request()
        expired_token = jose_jwt.encode(
            {"sub": "user@example.com", "roles": ["user"], "exp": int(time.time()) - 3600},
            security_module.JWT_SECRET,
            algorithm=security_module.JWT_ALGORITHM,
        )

        with pytest.raises(HTTPException) as exc_info:
            security_module.get_current_user_sse(
                request=request,
                access_token=expired_token,
                creds=None,
            )

        assert exc_info.value.status_code == 401

    def test_original_get_current_user_ignores_query_param(self, security_module):
        request = _make_request()
        token = _make_valid_token(security_module)

        with pytest.raises(HTTPException) as exc_info:
            security_module.get_current_user(
                request=request,
                creds=None,
            )

        assert exc_info.value.status_code == 401