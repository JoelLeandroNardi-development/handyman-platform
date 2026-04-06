from __future__ import annotations

import pytest
from fastapi import HTTPException

from tests.service_loader import load_service_app_module

@pytest.fixture(scope="module")
def rbac_module():
    return load_service_app_module(
        "gateway-service",
        "utils/rbac",
        package_name="gateway_rbac_test_app",
    )

@pytest.mark.unit
class TestRequireRole:
    def test_matching_role_passes(self, rbac_module):
        rbac_module.require_role({"roles": ["admin"]}, ["admin"])

    def test_case_insensitive(self, rbac_module):
        rbac_module.require_role({"roles": ["Admin"]}, ["admin"])
        rbac_module.require_role({"roles": ["CUSTOMER"]}, ["customer"])

    def test_one_of_many_matches(self, rbac_module):
        rbac_module.require_role({"roles": ["customer"]}, ["admin", "customer"])

    def test_disjoint_raises_403(self, rbac_module):
        with pytest.raises(HTTPException) as exc_info:
            rbac_module.require_role({"roles": ["customer"]}, ["admin"])
        assert exc_info.value.status_code == 403

    def test_empty_roles_raises_403(self, rbac_module):
        with pytest.raises(HTTPException) as exc_info:
            rbac_module.require_role({"roles": []}, ["admin"])
        assert exc_info.value.status_code == 403

    def test_missing_roles_key_raises_403(self, rbac_module):
        with pytest.raises(HTTPException) as exc_info:
            rbac_module.require_role({}, ["admin"])
        assert exc_info.value.status_code == 403

    def test_roles_not_list_raises_403(self, rbac_module):
        with pytest.raises(HTTPException) as exc_info:
            rbac_module.require_role({"roles": "admin"}, ["admin"])
        assert exc_info.value.status_code == 403

    def test_none_roles_raises_403(self, rbac_module):
        with pytest.raises(HTTPException) as exc_info:
            rbac_module.require_role({"roles": None}, ["admin"])
        assert exc_info.value.status_code == 403

    def test_multiple_token_roles_match(self, rbac_module):
        rbac_module.require_role({"roles": ["customer", "handyman"]}, ["handyman"])