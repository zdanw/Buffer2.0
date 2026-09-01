"""QDS replay identity: seed + policy + candidates + frozen history."""

from bebcare.services.quality_diversity_policy import SELECTOR_POLICY_VERSION
from bebcare.services.quality_diversity_select import (
    eligible_pool,
    history_from_snapshot,
    run_grounded_quality_diversity,
)
from tests.unit.qds_semantic_fixtures import scored_candidate_images


def _run(*, seed, history, source="studio", task_mode=None, preferred=None, risk_hint=None):
    images, intel = scored_candidate_images(
        preferred_index=0 if preferred else None,
    )
    if preferred:
        images[0].is_preferred = True
    return run_grounded_quality_diversity(
        products=images,
        scenes=[],
        intel_by_id=intel,
        target_aspect=1.0,
        count=2,
        use_scene=False,
        seed=seed,
        source=source,
        task_mode=task_mode,
        history=history,
        risk_hint=risk_hint or {"content_purpose": "lifestyle"},
    )


def test_semantic_fixture_pool_exclusions_and_spread():
    images, intel = scored_candidate_images()
    scored = []
    from bebcare.services.quality_diversity_select import score_images

    scored = score_images(images, role="primary_geometry", intel_by_id=intel, target_aspect=1.0)
    by_id = {c.image_id: c for c in scored}
    assert by_id["geo-000"].eligible is True
    assert by_id["geo-001"].eligible is True
    assert by_id["geo-003"].eligible is False
    assert "lifestyle_context_dominated" in by_id["geo-003"].verdict.exclusion_reasons
    assert by_id["geo-004"].eligible is False
    assert "packaging_dominated" in by_id["geo-004"].verdict.exclusion_reasons
    pool, info = eligible_pool(scored, require_semantic=True, max_size=3, role="primary_geometry")
    assert 2 <= len(pool) <= 3
    spread = max(c.score for c in pool) - min(c.score for c in pool)
    assert spread >= 0.08
    assert info["excluded"]


def test_weighted_and_conservative_and_preferred():
    weighted = _run(seed="w-1", history=[], source="studio")
    assert weighted.trace["selector_policy_version"] == SELECTOR_POLICY_VERSION
    assert weighted.trace["weighted_rotation_enabled"] is True
    assert weighted.trace["selection_reason"] == "weighted_eligible_pool"
    assert weighted.trace["effective_weights"]
    assert 2 <= len(weighted.trace["eligible_candidate_ids"]) <= 3
    conservative = _run(
        seed="w-1",
        history=[],
        source="automation",
        task_mode="auto",
        risk_hint={"auto_publish": True, "content_purpose": "lifestyle"},
    )
    assert conservative.trace["selection_reason"] in ("conservative_top", "preferred_authority", "single_eligible")
    preferred = _run(seed="w-1", history=[], preferred=True)
    assert preferred.selected[0][0].image_id == "geo-000"
    assert preferred.selected[0][1] in ("preferred", "suitability")
    assert preferred.selected[0][2].get("role") == "primary_geometry"
    for _img, _action, meta in preferred.selected[1:]:
        assert meta.get("role") == "secondary_structure"


def test_frozen_history_replay_vs_live_cooldown():
    first = _run(seed="replay-74", history=[])
    snapshot = first.trace["history_snapshot"]
    replay = _run(seed="replay-74", history=history_from_snapshot(snapshot))
    assert replay.selected[0][0].image_id == first.selected[0][0].image_id
    assert replay.trace["selected_ids"] == first.trace["selected_ids"]
    fake_history = [
        {
            "run_id": "prior-1",
            "primary_reference_id": first.selected[0][0].image_id,
            "primary_view_class": "front",
            "combination": first.selected[0][0].image_id,
            "fingerprint": {},
        }
    ]
    cooled = _run(seed="replay-74", history=fake_history)
    assert cooled.trace["diversity_penalties"]
    other_seed = _run(seed="replay-74-b", history=[])
    assert all(sid != "geo-003" and sid != "geo-004" for sid in first.trace["selected_ids"])
    primaries = {first.selected[0][0].image_id}
    for i in range(12):
        row = _run(seed=f"vary-{i}", history=[])
        primaries.add(row.selected[0][0].image_id)
    assert primaries <= {"geo-000", "geo-001", "geo-002"}
    assert len(primaries) >= 2
