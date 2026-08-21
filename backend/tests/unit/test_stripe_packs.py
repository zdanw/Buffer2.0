import pytest
from bebcare.billing.packs import parse_credit_packs, is_billing_enabled


def test_parse_credit_packs_ok():
    packs = parse_credit_packs(
        '[{"price_id":"price_a","credits":20,"label":"20 shots"}]'
    )
    assert len(packs) == 1
    assert packs[0].price_id == "price_a"
    assert packs[0].credits == 20
    assert packs[0].label == "20 shots"


def test_parse_credit_packs_rejects_bad_credits():
    with pytest.raises(ValueError):
        parse_credit_packs('[{"price_id":"price_a","credits":0,"label":"x"}]')


def test_billing_disabled_without_key(monkeypatch):
    from bebcare.config import settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "stripe_secret_key", None)
    monkeypatch.setattr(
        settings_mod.settings,
        "stripe_credit_packs",
        '[{"price_id":"price_a","credits":20,"label":"20"}]',
    )
    assert is_billing_enabled() is False
