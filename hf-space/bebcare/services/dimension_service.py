import logging
import secrets

logger = logging.getLogger(__name__)

from sqlalchemy.orm import Session
from bebcare.models.prompt_dimension import (
    PromptDimension,
    PromptDimensionCompatibility,
    PromptDimensionCompatPolicy,
    DimensionType,
    CompatMode,
)
from bebcare.prompt_builder.dimensions_data import DIMENSIONS
from bebcare.schemas.prompt_dimension import COMPAT_TARGET_TYPES


def generate_random_item_id() -> str:
    """Random machine ID for user-created visual styles (not derived from display name)."""
    return f"style_{secrets.token_hex(6)}"


def allocate_item_id_for_create(
    db: Session,
    product_type: str,
    dimension_type: str,
) -> str:
    """Return a random item_id unique within (product_type, dimension_type)."""
    return resolve_unique_item_id(
        db,
        product_type,
        dimension_type,
        generate_random_item_id(),
    )


def resolve_unique_item_id(
    db: Session,
    product_type: str,
    dimension_type: str,
    base_id: str,
    *,
    max_attempts: int = 100,
) -> str:
    """Ensure item_id is unique within (product_type, dimension_type). Appends _2, _3, … on clash."""
    base = (base_id or "").strip()[:100]
    if not base:
        base = "style"

    candidate = base
    for n in range(2, max_attempts + 2):
        exists = (
            db.query(PromptDimension)
            .filter(
                PromptDimension.product_type == product_type,
                PromptDimension.dimension_type == dimension_type,
                PromptDimension.item_id == candidate,
            )
            .first()
        )
        if not exists:
            return candidate
        suffix = f"_{n}"
        candidate = f"{base[: max(1, 100 - len(suffix))]}{suffix}"

    raise ValueError(f"Could not allocate unique item_id for '{base_id}'")


def _compat_entries_for_dim(dim: PromptDimension) -> dict:
    """返回 {target_type: {"mode": ..., "items": [...]}}，供生成链路使用。"""
    policy_by_type = {
        p.target_dimension_type: p.mode
        for p in (dim.compat_policies or [])
    }
    allow_items = {t: [] for t in COMPAT_TARGET_TYPES}
    block_items = {t: [] for t in COMPAT_TARGET_TYPES}

    for comp in dim.compatibilities or []:
        t = comp.target_dimension_type
        if t not in allow_items:
            continue
        rel = comp.relation_type or "compatible"
        if rel == "blocked":
            block_items[t].append(comp.target_item_id)
        else:
            allow_items[t].append(comp.target_item_id)

    result = {}
    for t in COMPAT_TARGET_TYPES:
        mode = policy_by_type.get(t) or CompatMode.UNRESTRICTED.value
        if mode == CompatMode.ALLOWLIST.value:
            # 空 items = 都不兼容
            result[t] = {"mode": "allowlist", "items": allow_items[t]}
        elif mode == CompatMode.BLOCKLIST.value and block_items[t]:
            result[t] = {"mode": "blocklist", "items": block_items[t]}
        else:
            result[t] = {"mode": "unrestricted", "items": []}
    return result


def _apply_compat_to_dim_dict(dim_dict: dict, dim: PromptDimension) -> dict:
    for key, entry in _compat_entries_for_dim(dim).items():
        dim_dict[f"compatible_{key}_mode"] = entry["mode"]
        if entry["mode"] in ("allowlist", "blocklist") and entry["items"]:
            dim_dict[f"compatible_{key}"] = entry["items"]
    return dim_dict


class DimensionService:
    def __init__(self):
        self._cache_enabled = True

    def clear_cache(self):
        pass

    def get_dimensions_by_product_type(self, product_type: str, db: Session) -> dict:
        try:
            dimensions = db.query(PromptDimension).filter(
                PromptDimension.product_type.ilike(product_type),
                PromptDimension.enabled.is_(True),
            ).all()

            result = {dim_type.value: [] for dim_type in DimensionType}

            for dim in dimensions:
                dim_dict = {
                    "id": dim.item_id,
                    "name": dim.name
                }
                if dim.time:
                    dim_dict["time"] = dim.time
                if dim.lighting:
                    dim_dict["lighting"] = dim.lighting

                _apply_compat_to_dim_dict(dim_dict, dim)
                result[dim.dimension_type].append(dim_dict)

            return result

        except Exception as e:
            logger.exception('DimensionService.get_dimensions_by_product_type failed: %s', e)
            return {dim_type.value: [] for dim_type in DimensionType}

    def get_compatible_dimensions(
        self,
        db: Session,
        product_type: str,
        source_dim_type: str,
        source_item_id: str,
        target_dim_type: str
    ) -> list:
        try:
            all_target_dims = db.query(PromptDimension).filter(
                PromptDimension.product_type == product_type,
                PromptDimension.dimension_type == target_dim_type,
                PromptDimension.enabled.is_(True),
            ).all()

            source_dim = db.query(PromptDimension).filter(
                PromptDimension.product_type == product_type,
                PromptDimension.dimension_type == source_dim_type,
                PromptDimension.item_id == source_item_id,
                PromptDimension.enabled.is_(True),
            ).first()

            if not source_dim:
                return [{"id": dim.item_id, "name": dim.name} for dim in all_target_dims]

            entries = _compat_entries_for_dim(source_dim)
            entry = entries.get(target_dim_type) or {"mode": "unrestricted", "items": []}
            mode = entry["mode"]
            item_ids = set(entry["items"])

            if mode == "allowlist":
                # 空白名单 = 都不兼容，不回退到全部
                pool = [d for d in all_target_dims if d.item_id in item_ids]
            elif mode == "blocklist":
                pool = [d for d in all_target_dims if d.item_id not in item_ids]
            else:
                pool = all_target_dims

            return [{"id": dim.item_id, "name": dim.name} for dim in pool]

        except Exception:
            return []

    def get_dimensions_by_type(
        self,
        db: Session,
        product_type: str,
        dimension_type: str
    ) -> list:
        try:
            dimensions = db.query(PromptDimension).filter(
                PromptDimension.product_type == product_type,
                PromptDimension.dimension_type == dimension_type,
                PromptDimension.enabled.is_(True),
            ).order_by(PromptDimension.item_id).all()

            result = []
            for dim in dimensions:
                dim_dict = {
                    "dimension_id": dim.dimension_id,
                    "id": dim.item_id,
                    "name": dim.name
                }
                if dim.time:
                    dim_dict["time"] = dim.time
                if dim.lighting:
                    dim_dict["lighting"] = dim.lighting

                _apply_compat_to_dim_dict(dim_dict, dim)
                result.append(dim_dict)

            return result

        except Exception as e:
            logger.exception('DimensionService.get_dimensions_by_type failed: %s', e)
            return []

    def initialize_default_dimensions(self, db: Session):
        db.query(PromptDimensionCompatibility).delete()
        db.query(PromptDimensionCompatPolicy).delete()
        db.query(PromptDimension).delete()
        db.commit()

        # 初始七大维度一律全部兼容（无策略行 = unrestricted）
        for product_type, product_dimensions in DIMENSIONS.items():
            for dim_type, items in product_dimensions.items():
                for item in items:
                    db.add(
                        PromptDimension(
                            product_type=product_type,
                            dimension_type=dim_type,
                            item_id=item["id"],
                            name=item["name"],
                        )
                    )

        db.commit()
        self.clear_cache()

        return {"status": "success", "message": "默认维度数据已初始化"}

    def reset_visual_styles(self, db: Session, pack_id: str = "general") -> dict:
        """Wipe all prompt dimensions and import a single pack."""
        from bebcare.services.vertical_pack_service import initialize_pack

        db.query(PromptDimensionCompatibility).delete()
        db.query(PromptDimensionCompatPolicy).delete()
        db.query(PromptDimension).delete()
        db.commit()
        self.clear_cache()
        result = initialize_pack(pack_id, db)
        return {
            "status": "success",
            "pack_id": pack_id,
            "message": f"Visual styles reset and imported from pack '{pack_id}'",
            **{k: v for k, v in result.items() if k not in ("status", "message")},
        }


dimension_service = DimensionService()
