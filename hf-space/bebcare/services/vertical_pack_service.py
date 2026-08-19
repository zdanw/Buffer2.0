"""Load vertical style packs and seed prompt dimensions."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from bebcare.models.prompt_dimension import PromptDimension
from bebcare.models.user import User
from bebcare.services.ownership import stamp_owner

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_PACK_DIR = _DATA_DIR / "vertical_packs"


def _pack_path(pack_id: str) -> Path:
    return _PACK_DIR / f"{pack_id}.json"


def list_packs() -> List[Dict[str, str]]:
    packs: List[Dict[str, str]] = []
    if not _PACK_DIR.exists():
        return packs
    for path in sorted(_PACK_DIR.glob("*.json")):
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
            packs.append(
                {
                    "id": meta.get("id") or path.stem,
                    "name": meta.get("name") or path.stem,
                    "description": meta.get("description") or "",
                }
            )
        except Exception:
            logger.exception("Failed to read pack %s", path)
    return packs


def _load_pack_meta(pack_id: str) -> Dict[str, Any]:
    path = _pack_path(pack_id)
    if not path.exists():
        raise FileNotFoundError(f"Vertical pack '{pack_id}' not found")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_dimensions_block(pack_id: str) -> Dict[str, Dict[str, list]]:
    meta = _load_pack_meta(pack_id)
    if "dimensions" in meta:
        return meta["dimensions"]

    snapshot_rel = meta.get("snapshot_file")
    if snapshot_rel:
        snapshot_path = _DATA_DIR / snapshot_rel
        if snapshot_path.exists():
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            return snapshot.get("dimensions") or {}

    from bebcare.prompt_builder.dimensions_data import DIMENSIONS

    product_types = meta.get("product_types") or []
    return {pt: DIMENSIONS[pt] for pt in product_types if pt in DIMENSIONS}


def get_product_types_for_pack(pack_id: str) -> List[str]:
    meta = _load_pack_meta(pack_id)
    if meta.get("product_types"):
        return list(meta["product_types"])
    return list(_load_dimensions_block(pack_id).keys())


def get_dimensions_for_pack(pack_id: str, product_type: str) -> Optional[Dict[str, list]]:
    block = _load_dimensions_block(pack_id)
    return block.get(product_type)


def initialize_pack(
    pack_id: str,
    db: Session,
    owner: User,
    *,
    replace_existing: bool = False,
) -> Dict[str, Any]:
    """Seed prompt_dimensions from a vertical pack for one owner."""
    dimensions_by_type = _load_dimensions_block(pack_id)
    if not dimensions_by_type:
        return {"status": "error", "message": f"No dimensions found for pack '{pack_id}'"}

    product_types = list(dimensions_by_type.keys())
    created = 0
    skipped = 0

    if replace_existing:
        db.query(PromptDimension).filter(
            PromptDimension.owner_user_id == owner.user_id,
            PromptDimension.product_type.in_(product_types),
        ).delete(synchronize_session=False)
        db.commit()

    for product_type, product_dimensions in dimensions_by_type.items():
        for dim_type, items in product_dimensions.items():
            for item in items:
                exists = (
                    db.query(PromptDimension)
                    .filter(
                        PromptDimension.owner_user_id == owner.user_id,
                        PromptDimension.product_type == product_type,
                        PromptDimension.dimension_type == dim_type,
                        PromptDimension.item_id == item["id"],
                    )
                    .first()
                )
                if exists:
                    skipped += 1
                    continue
                row = PromptDimension(
                    product_type=product_type,
                    dimension_type=dim_type,
                    item_id=item["id"],
                    name=item["name"],
                    time=item.get("time"),
                    lighting=item.get("lighting"),
                )
                stamp_owner(row, owner)
                db.add(row)
                created += 1

    db.commit()
    return {
        "status": "success",
        "pack_id": pack_id,
        "product_types": product_types,
        "created": created,
        "skipped": skipped,
        "message": f"Pack '{pack_id}' initialized ({created} created, {skipped} skipped)",
    }
