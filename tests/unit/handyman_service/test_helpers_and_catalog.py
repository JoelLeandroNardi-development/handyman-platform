from __future__ import annotations

import pytest

from tests.service_loader import load_service_app_module

_PKG = "handyman_helpers_test_app"

@pytest.fixture(scope="module")
def helpers_module():
    return load_service_app_module(
        "handyman-service",
        "application/helpers",
        package_name=_PKG,
        reload_modules=True,
    )

@pytest.fixture(scope="module")
def catalog_module():
    return load_service_app_module(
        "handyman-service",
        "domain/skills_catalog",
        package_name=_PKG,
    )

@pytest.mark.unit
class TestLabelFromKey:
    @pytest.mark.parametrize("key, expected", [
        ("plumbing", "Plumbing"),
        ("ceiling_fan_installation", "Ceiling Fan Installation"),
        ("", ""),
        ("  already_spaced  ", "Already Spaced"),
    ])
    def test_converts(self, helpers_module, key, expected):
        assert helpers_module.label_from_key(key) == expected

@pytest.mark.unit
class TestNormalizeSkillKey:
    @pytest.mark.parametrize("raw, expected", [
        ("Plumbing", "plumbing"),
        ("  TRIM  ", "trim"),
        ("", ""),
        (None, ""),
    ])
    def test_normalises(self, helpers_module, raw, expected):
        assert helpers_module.normalize_skill_key(raw) == expected

@pytest.mark.unit
class TestNormalizeCatalog:
    def test_lowercases_and_deduplicates(self, helpers_module):
        result = helpers_module.normalize_catalog({
            "Plumbing": ["Leak_Repair", "leak_repair", "Pipe"],
        })
        assert result == {"plumbing": ["leak_repair", "pipe"]}

    def test_skips_empty_categories(self, helpers_module):
        result = helpers_module.normalize_catalog({
            "": ["skill1"],
            "valid": ["skill2"],
        })
        assert "" not in result
        assert "valid" in result

    def test_skips_empty_skills(self, helpers_module):
        result = helpers_module.normalize_catalog({
            "cat": ["", "  ", "real_skill"],
        })
        assert result == {"cat": ["real_skill"]}

    def test_none_input(self, helpers_module):
        assert helpers_module.normalize_catalog(None) == {}

    def test_category_with_only_blanks_excluded(self, helpers_module):
        result = helpers_module.normalize_catalog({"cat": ["", "  "]})
        assert result == {}

@pytest.mark.unit
class TestValidateCatalogShape:
    def test_valid_catalog_passes(self, helpers_module):
        helpers_module.validate_catalog_shape({"plumbing": ["leak"]})

    def test_empty_payload_raises(self, helpers_module):
        with pytest.raises(ValueError, match="at least one category"):
            helpers_module.validate_catalog_shape({})

    def test_none_raises(self, helpers_module):
        with pytest.raises(ValueError, match="at least one category"):
            helpers_module.validate_catalog_shape(None)

    def test_cross_category_duplicates_raise(self, helpers_module):
        with pytest.raises(ValueError, match="Duplicate skill keys"):
            helpers_module.validate_catalog_shape({
                "plumbing": ["shared_skill"],
                "electrical": ["shared_skill"],
            })

@pytest.mark.unit
class TestNormalizeSkillsInput:
    def test_lowercases_and_deduplicates(self, helpers_module):
        result = helpers_module.normalize_skills_input(["Plumbing", "plumbing", "Electrical"])
        assert result == ["plumbing", "electrical"]

    def test_strips_blanks(self, helpers_module):
        result = helpers_module.normalize_skills_input(["", "  ", "real"])
        assert result == ["real"]

    def test_none_input(self, helpers_module):
        assert helpers_module.normalize_skills_input(None) == []

    def test_preserves_order(self, helpers_module):
        result = helpers_module.normalize_skills_input(["b", "a", "c"])
        assert result == ["b", "a", "c"]

@pytest.mark.unit
class TestDefaultSkillsCatalog:
    def test_is_nonempty_dict(self, catalog_module):
        catalog = catalog_module.DEFAULT_SKILLS_CATALOG
        assert isinstance(catalog, dict)
        assert len(catalog) > 0

    def test_all_categories_have_skills(self, catalog_module):
        for cat, skills in catalog_module.DEFAULT_SKILLS_CATALOG.items():
            assert isinstance(skills, list), f"Category {cat} is not a list"
            assert len(skills) > 0, f"Category {cat} is empty"

    def test_no_duplicate_skills_across_categories(self, catalog_module):
        seen: set[str] = set()
        for cat, skills in catalog_module.DEFAULT_SKILLS_CATALOG.items():
            for skill in skills:
                assert skill not in seen, f"Duplicate skill '{skill}' in '{cat}'"
                seen.add(skill)

    def test_all_keys_are_snake_case(self, catalog_module):
        import re
        pattern = re.compile(r"^[a-z][a-z0-9_]+$")
        for cat, skills in catalog_module.DEFAULT_SKILLS_CATALOG.items():
            assert pattern.match(cat), f"Category key '{cat}' not snake_case"
            for skill in skills:
                assert pattern.match(skill), f"Skill key '{skill}' in '{cat}' not snake_case"