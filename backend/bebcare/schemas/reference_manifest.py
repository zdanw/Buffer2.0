from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

ManifestRole = Literal["primary_subject", "supporting_subject", "scene"]
ManifestAuthority = Literal["explicit_pin", "preferred", "suitability", "legacy_url"]
ManifestImageType = Literal["product", "scene"]
MANIFEST_VERSION = "ref_manifest_v1"


class ManifestItem(BaseModel):
    order: int
    role: ManifestRole
    image_id: Optional[str] = None
    cdn_url: str
    image_type: ManifestImageType
    authority: ManifestAuthority
    suitability: Optional[dict[str, Any]] = None


class ReferenceManifest(BaseModel):
    version: Literal["ref_manifest_v1"] = MANIFEST_VERSION
    items: list[ManifestItem] = Field(default_factory=list)

    def ordered_urls(self) -> list[str]:
        return [item.cdn_url for item in sorted(self.items, key=lambda i: i.order) if item.cdn_url]

    def product_urls(self) -> list[str]:
        return [
            item.cdn_url
            for item in sorted(self.items, key=lambda i: i.order)
            if item.image_type == "product" and item.cdn_url
        ]

    def scene_urls(self) -> list[str]:
        return [
            item.cdn_url
            for item in sorted(self.items, key=lambda i: i.order)
            if item.image_type == "scene" and item.cdn_url
        ]

    def product_ids(self) -> list[str]:
        return [
            item.image_id
            for item in sorted(self.items, key=lambda i: i.order)
            if item.image_type == "product" and item.image_id
        ]

    def scene_ids(self) -> list[str]:
        return [
            item.image_id
            for item in sorted(self.items, key=lambda i: i.order)
            if item.image_type == "scene" and item.image_id
        ]

    def primary_image_id(self) -> Optional[str]:
        for item in sorted(self.items, key=lambda i: i.order):
            if item.role == "primary_subject":
                return item.image_id
        return None


def assert_canonical_grounded_order(manifest: ReferenceManifest) -> None:
    """primary, then supporting by order, then at most one scene last."""
    ordered = sorted(manifest.items, key=lambda i: i.order)
    roles = [item.role for item in ordered]
    scene_indexes = [i for i, role in enumerate(roles) if role == "scene"]
    if len(scene_indexes) > 1:
        raise ValueError("Grounded manifest may include at most one scene")
    if scene_indexes and scene_indexes[0] != len(roles) - 1:
        raise ValueError("Grounded manifest must place scene last")
    if roles and roles[0] != "primary_subject":
        raise ValueError("Grounded manifest must start with primary_subject")
    supporting = [r for r in roles if r == "supporting_subject"]
    expected_mid = ["supporting_subject"] * len(supporting)
    mid = [r for r in roles[1:] if r != "scene"]
    if mid != expected_mid:
        raise ValueError("Grounded supporting_subject items must follow primary in order")
