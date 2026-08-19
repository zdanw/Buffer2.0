from bebcare.prompt_builder.dimensions_data import DIMENSIONS
from bebcare.prompt_builder.prompt_engine import PromptEngine


class _EmptyDimService:
    def get_dimensions_by_product_type(self, product_type, db, **kwargs):
        return {
            "scenes": [],
            "lighting": [],
            "styles": [],
            "details": [],
            "viewpoints": [],
            "compositions": [],
            "quality": [],
        }


class _PartialDimService:
    """DB has styles but no scenes — must still use DB, not Night Lights."""

    def get_dimensions_by_product_type(self, product_type, db, **kwargs):
        return {
            "scenes": [],
            "lighting": [],
            "styles": [{"id": "s1", "name": "Custom Style"}],
            "details": [],
            "viewpoints": [],
            "compositions": [],
            "quality": [],
        }


def test_unknown_type_does_not_fallback_to_night_lights(monkeypatch):
    engine = PromptEngine()
    import bebcare.prompt_builder.prompt_engine as pe

    monkeypatch.setattr(pe, "dimension_service", _EmptyDimService())
    dims = engine._get_dimensions("Brand New Category", db=object())
    assert dims["scenes"] == []
    assert dims["styles"] == []
    # Must not silently borrow Night Lights seed data
    assert dims != DIMENSIONS["Night Lights"]
    assert not any(dims.values())


def test_db_partial_dims_used_even_without_scenes(monkeypatch):
    engine = PromptEngine()
    import bebcare.prompt_builder.prompt_engine as pe

    monkeypatch.setattr(pe, "dimension_service", _PartialDimService())
    dims = engine._get_dimensions("Air Purifiers", db=object())
    assert dims["styles"][0]["id"] == "s1"
    assert dims["scenes"] == []


def test_known_static_type_still_loads_when_db_empty(monkeypatch):
    engine = PromptEngine()
    import bebcare.prompt_builder.prompt_engine as pe

    monkeypatch.setattr(pe, "dimension_service", _EmptyDimService())
    dims = engine._get_dimensions("Night Lights", db=object())
    assert dims is DIMENSIONS["Night Lights"] or dims == DIMENSIONS["Night Lights"]
    assert dims.get("scenes")
