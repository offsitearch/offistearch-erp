"""Unit tests for the kernel org-level RBAC + financial-access policy.

Ports the truth table from the reference suite ``test_financial_policy.py``,
using a lightweight principal instead of the ORM User model.
"""

import pytest

from studioerp.rbac import (
    FINANCIAL_LEVEL,
    LEVEL_RANK,
    ExecutiveLevels,
    has_financial_access,
    has_min_level,
    is_staff_band,
    level_rank,
    user_level_rank,
)


class _OrgLevel:
    def __init__(self, code: str | None):
        self.code = code


class _Principal:
    def __init__(self, code: str | None):
        self.org_level = _OrgLevel(code)


def _user_at(code: str | None):
    return _Principal(code)


class TestFinancialAccessTruthTable:
    @pytest.mark.parametrize("code", ["L0", "L1"])
    def test_ceo_and_director_allowed(self, code):
        assert has_financial_access(_user_at(code)) is True

    @pytest.mark.parametrize("code", ["L2", "L3", "L4", "L5", "L6"])
    def test_all_other_levels_denied(self, code):
        assert has_financial_access(_user_at(code)) is False

    def test_user_without_level_denied(self):
        assert has_financial_access(_user_at(None)) is False

    def test_unknown_level_code_denied(self):
        assert has_financial_access(_user_at("LX")) is False


def test_shared_constant_is_director_floor():
    assert FINANCIAL_LEVEL == "L1"


def test_financial_boundary_matches_executive_band():
    assert set(ExecutiveLevels) == {"L0", FINANCIAL_LEVEL}


class TestLevelRanks:
    def test_rank_is_lower_for_senior(self):
        assert LEVEL_RANK["L0"] < LEVEL_RANK["L1"] < LEVEL_RANK["L6"]

    def test_unknown_level_is_least_privileged(self):
        assert level_rank("L9") > LEVEL_RANK["L6"]
        assert level_rank(None) > LEVEL_RANK["L6"]

    def test_user_level_rank(self):
        assert user_level_rank(_user_at("L2")) == 2


class TestMinLevel:
    def test_has_min_level_senior_and_same(self):
        assert has_min_level(_user_at("L1"), "L2") is True
        assert has_min_level(_user_at("L2"), "L2") is True

    def test_has_min_level_rejects_junior(self):
        assert has_min_level(_user_at("L3"), "L2") is False


class TestStaffBand:
    @pytest.mark.parametrize("code", ["L4", "L5", "L6", None])
    def test_staff_band_true_for_L4_plus_unknown(self, code):
        assert is_staff_band(_user_at(code)) is True

    @pytest.mark.parametrize("code", ["L0", "L1", "L2", "L3"])
    def test_staff_band_false_for_leadership(self, code):
        assert is_staff_band(_user_at(code)) is False
