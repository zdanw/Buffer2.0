"""Unit tests for brand context resolution."""

from bebcare.models import Brand, Product, GENERIC_BRAND_ID, BEBCARE_BRAND_ID
from bebcare.services.brand_context import resolve_product_brand_context


def _make_brand(**kwargs) -> Brand:
    defaults = {
        "brand_id": GENERIC_BRAND_ID,
        "slug": "generic",
        "name": "Generic",
        "is_generic": True,
        "is_system": True,
        "voice": None,
        "vertical_pack": "general",
        "copy_fallback_selling_points": [],
        "narrative_perspectives": [],
        "writing_styles": [],
    }
    defaults.update(kwargs)
    return Brand(**defaults)


def _make_product(**kwargs) -> Product:
    defaults = {
        "product_id": "prod-1",
        "product_name": "Test Product",
        "category": "General",
        "description": "A test product",
        "selling_points": None,
        "brand_voice": None,
        "use_brand_voice": True,
        "brand_id": GENERIC_BRAND_ID,
    }
    defaults.update(kwargs)
    product = Product(**defaults)
    if "brand" in kwargs:
        product.brand = kwargs["brand"]
    return product


class FakeSession:
    def __init__(self, brands: dict[str, Brand]):
        self._brands = brands

    def query(self, model):
        return self

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None


def test_generic_product_has_no_baby_fallbacks():
    generic = _make_brand()
    product = _make_product(brand=generic)
    product.brand_id = GENERIC_BRAND_ID

    class Session:
        def query(self, model):
            return self

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return generic

    ctx = resolve_product_brand_context(Session(), product)
    assert ctx["is_generic_brand"] is True
    assert ctx["brand_voice"] == ""
    assert ctx["selling_points"] == []
    assert "全球父母" not in str(ctx.get("copy_fallback_selling_points", ""))


def test_bebcare_product_gets_brand_voice_and_perspectives():
    bebcare = _make_brand(
        brand_id=BEBCARE_BRAND_ID,
        slug="bebcare",
        name="Bebcare",
        is_generic=False,
        voice="专业且温暖",
        vertical_pack="baby_family",
        copy_fallback_selling_points=["高品质产品", "全球父母信赖"],
        copy_example="Nighttime just got sweeter!",
        narrative_perspectives=[{"id": "new_parent", "name": "新手父母", "description": "育儿"}],
    )
    product = _make_product(brand_id=BEBCARE_BRAND_ID, brand=bebcare)

    class Session:
        def query(self, model):
            return self

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return bebcare

    ctx = resolve_product_brand_context(Session(), product)
    assert ctx["brand_voice"] == "专业且温暖"
    assert ctx["copy_example"] == "Nighttime just got sweeter!"
    assert len(ctx["narrative_perspectives"]) == 1
    assert ctx["copy_fallback_selling_points"] == ["高品质产品", "全球父母信赖"]


def test_product_override_voice_wins():
    bebcare = _make_brand(
        brand_id=BEBCARE_BRAND_ID,
        slug="bebcare",
        name="Bebcare",
        is_generic=False,
        voice="专业且温暖",
    )
    product = _make_product(
        brand_id=BEBCARE_BRAND_ID,
        brand=bebcare,
        brand_voice="Playful and bold",
    )

    class Session:
        def query(self, model):
            return self

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return bebcare

    ctx = resolve_product_brand_context(Session(), product)
    assert ctx["brand_voice"] == "Playful and bold"


def test_use_brand_voice_false_clears_voice():
    bebcare = _make_brand(
        brand_id=BEBCARE_BRAND_ID,
        slug="bebcare",
        name="Bebcare",
        is_generic=False,
        voice="专业且温暖",
    )
    product = _make_product(
        brand_id=BEBCARE_BRAND_ID,
        brand=bebcare,
        brand_voice="Override",
        use_brand_voice=False,
    )

    class Session:
        def query(self, model):
            return self

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return bebcare

    ctx = resolve_product_brand_context(Session(), product)
    assert ctx["brand_voice"] == ""
