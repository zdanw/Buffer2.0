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
    dims = engine._get_dimensions("Air Purifiers", db=object(), owner_user_id="owner-1")
    assert dims["styles"][0]["id"] == "s1"
    assert dims["scenes"] == []


def test_missing_owner_does_not_query_all_users_dimensions(monkeypatch):
    class _Spy:
        called = False

        def get_dimensions_by_product_type(self, product_type, db, **kwargs):
            self.called = True
            return {
                "scenes": [{"id": "leaked", "name": "Other User Scene"}],
                "lighting": [],
                "styles": [],
                "details": [],
                "viewpoints": [],
                "compositions": [],
                "quality": [],
            }

    spy = _Spy()
    engine = PromptEngine()
    import bebcare.prompt_builder.prompt_engine as pe

    monkeypatch.setattr(pe, "dimension_service", spy)
    dims = engine._get_dimensions("Night Lights", db=object())
    assert spy.called is False
    assert dims.get("scenes")
    assert dims["scenes"][0]["id"] != "leaked"


def test_owner_user_id_is_passed_to_dimension_service(monkeypatch):
    seen = {}

    class _Spy:
        def get_dimensions_by_product_type(self, product_type, db, **kwargs):
            seen["owner_user_id"] = kwargs.get("owner_user_id")
            return {
                "scenes": [{"id": "owned", "name": "Owned Scene"}],
                "lighting": [],
                "styles": [],
                "details": [],
                "viewpoints": [],
                "compositions": [],
                "quality": [],
            }

    engine = PromptEngine()
    import bebcare.prompt_builder.prompt_engine as pe

    monkeypatch.setattr(pe, "dimension_service", _Spy())
    dims = engine._get_dimensions("Custom Type", db=object(), owner_user_id="user-42")
    assert seen["owner_user_id"] == "user-42"
    assert dims["scenes"][0]["id"] == "owned"


def test_build_image_prompt_passes_owner_not_instance_state(monkeypatch):
    engine = PromptEngine()
    seen = []
    orig = engine._get_dimensions

    def _spy(product_type="Night Lights", db=None, owner_user_id=None):
        seen.append(owner_user_id)
        return orig(product_type, db, owner_user_id=owner_user_id)

    engine._get_dimensions = _spy
    engine.build_image_prompt(
        {
            "product_name": "Lamp",
            "description": "A lamp",
            "category": "Night Lights",
            "owner_user_id": "owner-7",
        },
        "instagram",
    )
    assert seen
    assert all(owner == "owner-7" for owner in seen)
    assert getattr(engine, "_dim_owner_user_id", None) is None


def test_known_static_type_still_loads_when_db_empty(monkeypatch):
    engine = PromptEngine()
    import bebcare.prompt_builder.prompt_engine as pe

    monkeypatch.setattr(pe, "dimension_service", _EmptyDimService())
    dims = engine._get_dimensions("Night Lights", db=object())
    assert dims is DIMENSIONS["Night Lights"] or dims == DIMENSIONS["Night Lights"]
    assert dims.get("scenes")
