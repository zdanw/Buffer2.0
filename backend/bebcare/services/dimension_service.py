import logging

logger = logging.getLogger(__name__)

from functools import lru_cache
from sqlalchemy.orm import Session
from bebcare.models.prompt_dimension import PromptDimension, PromptDimensionCompatibility, DimensionType
from bebcare.prompt_builder.dimensions_data import DIMENSIONS


class DimensionService:
    def __init__(self):
        self._cache_enabled = True

    def clear_cache(self):
        pass

    def get_dimensions_by_product_type(self, product_type: str, db: Session) -> dict:
        try:
            dimensions = db.query(PromptDimension).filter(
                PromptDimension.product_type.ilike(product_type)
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

                compatibilities = {
                    "scenes": [],
                    "lighting": [],
                    "styles": [],
                    "compositions": [],
                    "details": [],
                    "quality": [],
                    "viewpoints": [],
                }
                for comp in dim.compatibilities:
                    if comp.target_dimension_type in compatibilities:
                        compatibilities[comp.target_dimension_type].append(comp.target_item_id)
                
                for key, values in compatibilities.items():
                    if values:
                        dim_dict[f"compatible_{key}"] = values

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
            source_dim = db.query(PromptDimension).filter(
                PromptDimension.product_type == product_type,
                PromptDimension.dimension_type == source_dim_type,
                PromptDimension.item_id == source_item_id
            ).first()

            if not source_dim:
                all_target_dims = db.query(PromptDimension).filter(
                    PromptDimension.product_type == product_type,
                    PromptDimension.dimension_type == target_dim_type
                ).all()
                return [
                    {"id": dim.item_id, "name": dim.name}
                    for dim in all_target_dims
                ]

            compatible_item_ids = {
                comp.target_item_id
                for comp in source_dim.compatibilities
            }

            if not compatible_item_ids:
                all_target_dims = db.query(PromptDimension).filter(
                    PromptDimension.product_type == product_type,
                    PromptDimension.dimension_type == target_dim_type
                ).all()
                return [
                    {"id": dim.item_id, "name": dim.name}
                    for dim in all_target_dims
                ]

            compatible_dims = db.query(PromptDimension).filter(
                PromptDimension.product_type == product_type,
                PromptDimension.dimension_type == target_dim_type,
                PromptDimension.item_id.in_(compatible_item_ids)
            ).all()

            return [
                {"id": dim.item_id, "name": dim.name}
                for dim in compatible_dims
            ]

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
                PromptDimension.dimension_type == dimension_type
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

                compatibilities = {
                    "scenes": [],
                    "lighting": [],
                    "styles": [],
                    "compositions": [],
                    "details": [],
                    "quality": [],
                    "viewpoints": [],
                }
                for comp in dim.compatibilities:
                    if comp.target_dimension_type in compatibilities:
                        compatibilities[comp.target_dimension_type].append(comp.target_item_id)
                
                for key, values in compatibilities.items():
                    if values:
                        dim_dict[f"compatible_{key}"] = values

                result.append(dim_dict)

            return result

        except Exception as e:
            logger.exception('DimensionService.get_dimensions_by_type failed: %s', e)
            return []

    def initialize_default_dimensions(self, db: Session):
        db.query(PromptDimensionCompatibility).delete()
        db.query(PromptDimension).delete()
        db.commit()

        for product_type, product_dimensions in DIMENSIONS.items():
            for dim_type, items in product_dimensions.items():
                for item in items:
                    new_dim = PromptDimension(
                        product_type=product_type,
                        dimension_type=dim_type,
                        item_id=item["id"],
                        name=item["name"]
                    )
                    db.add(new_dim)
                    db.flush()

                    if "compatible_with" in item:
                        for target_item_id in item["compatible_with"]:
                            comp = PromptDimensionCompatibility(
                                dimension_id=new_dim.dimension_id,
                                source_dimension_type=dim_type,
                                target_dimension_type="scenes",
                                target_item_id=target_item_id,
                                relation_type="compatible",
                                is_active=True
                            )
                            db.add(comp)

        db.commit()
        self.clear_cache()

        return {"status": "success", "message": "默认维度数据已初始化"}


dimension_service = DimensionService()