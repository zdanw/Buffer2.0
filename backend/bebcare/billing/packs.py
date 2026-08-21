from __future__ import annotations

import json
from dataclasses import dataclass

from bebcare.config.settings import settings


@dataclass(frozen=True)
class CreditPack:
    price_id: str
    credits: int
    label: str


def parse_credit_packs(raw: str) -> list[CreditPack]:
    data = json.loads(raw or "[]")
    if not isinstance(data, list):
        raise ValueError("STRIPE_CREDIT_PACKS must be a JSON array")
    packs: list[CreditPack] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"pack[{i}] must be an object")
        price_id = str(item.get("price_id") or "").strip()
        label = str(item.get("label") or "").strip()
        credits = item.get("credits")
        if not price_id or not label:
            raise ValueError(f"pack[{i}] requires price_id and label")
        if not isinstance(credits, int) or credits < 1:
            raise ValueError(f"pack[{i}] credits must be int >= 1")
        packs.append(CreditPack(price_id=price_id, credits=credits, label=label))
    return packs


def get_credit_packs() -> list[CreditPack]:
    try:
        return parse_credit_packs(settings.stripe_credit_packs)
    except (ValueError, json.JSONDecodeError):
        return []


def find_pack(price_id: str) -> CreditPack | None:
    for p in get_credit_packs():
        if p.price_id == price_id:
            return p
    return None


def is_billing_enabled() -> bool:
    return bool(settings.stripe_secret_key) and len(get_credit_packs()) > 0
