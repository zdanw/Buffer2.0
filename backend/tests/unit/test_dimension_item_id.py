"""Tests for scoped visual style item_id uniqueness."""

import re
from unittest.mock import MagicMock

from bebcare.services.dimension_service import (
    allocate_item_id_for_create,
    generate_random_item_id,
    resolve_unique_item_id,
)


def _mock_db(first_results: list):
    mock_q = MagicMock()
    mock_q.filter.return_value = mock_q
    mock_q.first.side_effect = first_results
    mock_db = MagicMock()
    mock_db.query.return_value = mock_q
    return mock_db


def test_returns_base_when_unique():
    db = _mock_db([None])
    assert resolve_unique_item_id(db, "General", "scenes", "cozy_corner") == "cozy_corner"


def test_appends_suffix_on_conflict():
    db = _mock_db([object(), None])
    assert resolve_unique_item_id(db, "General", "scenes", "cozy_corner") == "cozy_corner_2"


def test_same_id_allowed_across_product_types():
    db = _mock_db([None])
    assert resolve_unique_item_id(db, "General", "scenes", "nursery") == "nursery"


def test_same_id_allowed_across_dimension_types():
    db = _mock_db([None])
    assert resolve_unique_item_id(db, "General", "scenes", "soft_morning") == "soft_morning"


def test_generate_random_item_id_format():
    item_id = generate_random_item_id()
    assert re.fullmatch(r"style_[0-9a-f]{12}", item_id)


def test_allocate_item_id_for_create_uses_random_base():
    db = _mock_db([None])
    item_id = allocate_item_id_for_create(db, "Breast Pump", "viewpoints")
    assert re.fullmatch(r"style_[0-9a-f]{12}", item_id)
