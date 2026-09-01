"""Cached-analysis fixtures for QDS weighted-pool tests. No provider calls."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from bebcare.schemas.asset_intelligence import AssetIntelligenceResult, PhysicalModule


def geometry_high(*, view="front"):
    return AssetIntelligenceResult(
        confidence="high",
        asset_source_type="product",
        generation_suitability="primary_subject",
        packaging_presence="absent",
        people_or_hands_presence="absent",
        broad_composition="centered",
        subject_or_scene="subject",
        physical=PhysicalModule(support_surface="table", broad_view_class=view, packaging_role="unknown"),
    )


def geometry_mid(*, view="side"):
    return AssetIntelligenceResult(
        confidence="high",
        asset_source_type="product",
        generation_suitability="supporting_subject",
        packaging_presence="absent",
        people_or_hands_presence="absent",
        broad_composition="centered",
        subject_or_scene="subject",
        physical=PhysicalModule(support_surface="table", broad_view_class=view, packaging_role="unknown"),
    )


def geometry_low(*, view="three_quarter"):
    return AssetIntelligenceResult(
        confidence="medium",
        asset_source_type="product",
        generation_suitability="supporting_subject",
        packaging_presence="absent",
        people_or_hands_presence="absent",
        broad_composition="close_up",
        subject_or_scene="subject",
        physical=PhysicalModule(support_surface="unknown", broad_view_class=view, packaging_role="unknown"),
    )


def lifestyle_excluded():
    return AssetIntelligenceResult(
        confidence="high",
        asset_source_type="scene",
        generation_suitability="scene",
        packaging_presence="absent",
        people_or_hands_presence="absent",
        broad_composition="wide",
        subject_or_scene="scene",
        physical=PhysicalModule(support_surface="unknown", broad_view_class="wide", packaging_role="unknown"),
    )


def packaging_excluded():
    return AssetIntelligenceResult(
        confidence="high",
        asset_source_type="packaging",
        generation_suitability="avoid_as_primary",
        packaging_presence="present",
        people_or_hands_presence="absent",
        broad_composition="centered",
        subject_or_scene="subject",
        physical=PhysicalModule(support_surface="unknown", broad_view_class="front", packaging_role="primary"),
    )


def scored_candidate_images(*, preferred_index: int | None = None):
    """Five product images: 3 geometry + lifestyle + packaging."""
    specs = [
        {"width": 2000, "height": 2000, "phash": "1111111111111111", "intel": geometry_high(view="front")},
        {"width": 700, "height": 700, "phash": "2222222222222222", "intel": geometry_mid(view="side")},
        {"width": 380, "height": 380, "phash": "3333333333333333", "intel": geometry_low(view="three_quarter")},
        {"width": 1800, "height": 1200, "phash": "4444444444444444", "intel": lifestyle_excluded()},
        {"width": 1400, "height": 1400, "phash": "5555555555555555", "intel": packaging_excluded()},
    ]
    images = []
    intel = {}
    for index, spec in enumerate(specs):
        image = SimpleNamespace(
            image_id=f"geo-{index:03d}",
            cdn_url=f"https://cdn.test/qds-fix-{index}.jpg",
            width=spec["width"],
            height=spec["height"],
            image_type="product",
            is_preferred=preferred_index == index,
            sort_index=index,
            uploaded_at=datetime(2026, 9, 1, 12, index),
            phash=spec["phash"],
            analysis_status="ready",
        )
        images.append(image)
        intel[image.image_id] = spec["intel"]
    return images, intel
