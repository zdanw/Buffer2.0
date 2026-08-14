"""Unit tests for visual style auto-seed (idempotent)."""

from unittest.mock import MagicMock, patch

from bebcare.services.visual_style_seed_service import seed_visual_styles_if_needed


class FakeQuery:
    def __init__(self, count: int):
        self._count = count

    def count(self):
        return self._count


class FakeSession:
    def __init__(self, count: int):
        self._count = count
        self.query_model = None

    def query(self, model):
        self.query_model = model
        return FakeQuery(self._count)


def test_empty_db_seeds_general_pack():
    db = FakeSession(0)
    with patch(
        "bebcare.services.visual_style_seed_service.initialize_pack",
        return_value={"status": "success", "pack_id": "general", "added": 10},
    ) as mock_init:
        with patch("bebcare.services.visual_style_seed_service.settings") as mock_settings:
            mock_settings.seed_baby_dimensions = False
            results = seed_visual_styles_if_needed(db)

    mock_init.assert_called_once_with("general", db)
    assert len(results) == 1
    assert results[0]["pack_id"] == "general"


def test_nonempty_db_skips_general_seed():
    db = FakeSession(42)
    with patch(
        "bebcare.services.visual_style_seed_service.initialize_pack",
    ) as mock_init:
        with patch("bebcare.services.visual_style_seed_service.settings") as mock_settings:
            mock_settings.seed_baby_dimensions = False
            results = seed_visual_styles_if_needed(db)

    mock_init.assert_not_called()
    assert results == []


def test_baby_flag_adds_pack_without_wiping():
    db = FakeSession(42)
    with patch(
        "bebcare.services.visual_style_seed_service.initialize_pack",
        return_value={"status": "success", "pack_id": "baby_family", "added": 5},
    ) as mock_init:
        with patch("bebcare.services.visual_style_seed_service.settings") as mock_settings:
            mock_settings.seed_baby_dimensions = True
            results = seed_visual_styles_if_needed(db)

    mock_init.assert_called_once_with("baby_family", db)
    assert len(results) == 1
    assert results[0]["pack_id"] == "baby_family"


def test_empty_db_with_baby_flag_seeds_both():
    db = FakeSession(0)
    with patch(
        "bebcare.services.visual_style_seed_service.initialize_pack",
        side_effect=[
            {"status": "success", "pack_id": "general", "added": 10},
            {"status": "success", "pack_id": "baby_family", "added": 5},
        ],
    ) as mock_init:
        with patch("bebcare.services.visual_style_seed_service.settings") as mock_settings:
            mock_settings.seed_baby_dimensions = True
            results = seed_visual_styles_if_needed(db)

    assert mock_init.call_count == 2
    assert [r["pack_id"] for r in results] == ["general", "baby_family"]
