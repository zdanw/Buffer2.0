"""Local selector comparison. Pins non-selector inputs. Does not call providers."""

from __future__ import annotations

from typing import Any

from bebcare.services.quality_diversity_policy import (
    SELECTOR_POLICY_VERSION,
    RiskBand,
)
from bebcare.services.quality_diversity_select import (
    ScoredCandidate,
    conservative_choice,
    eligible_pool,
    rng_from_seed,
    weighted_choice,
    weighted_primary_allowed,
    _effective_weights,
)


def pin_experiment_context(
    *,
    product_id: str,
    provider: str | None,
    model: str | None,
    aspect_ratio: str | None,
    content_purpose: str | None,
    quality_policy: str | None,
    source: str = "studio",
    task_mode: str | None = None,
    seed: str = "eval-pin",
) -> dict[str, Any]:
    return {
        "product_id": product_id,
        "provider": provider,
        "model": model,
        "aspect_ratio": aspect_ratio,
        "content_purpose": content_purpose,
        "quality_policy": quality_policy or SELECTOR_POLICY_VERSION,
        "source": source,
        "task_mode": task_mode,
        "seed": seed,
        "auto_provider_calls": False,
    }


def compare_selector_modes(
    scored: list[ScoredCandidate],
    *,
    seed: str | None = None,
    risk: RiskBand = "balanced",
    source: str = "studio",
    task_mode: str | None = None,
    penalties: dict[str, float] | None = None,
    pin: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare A current-top, B floor-top-one, C floor-weighted. No paid calls."""
    pinned = pin or pin_experiment_context(
        product_id="unspecified",
        provider=None,
        model=None,
        aspect_ratio=None,
        content_purpose=None,
        quality_policy=SELECTOR_POLICY_VERSION,
        source=source,
        task_mode=task_mode,
        seed=seed or "eval-1",
    )
    if pinned.get("auto_provider_calls"):
        raise RuntimeError("eval_provider_calls_forbidden")
    use_seed = str(seed or pinned.get("seed") or "eval-1")
    use_source = str(pinned.get("source") or source)
    use_mode = pinned.get("task_mode") if pinned.get("task_mode") is not None else task_mode
    current = max(scored, key=lambda c: (c.score, c.image_id)) if scored else None
    rotate_ok, reason, _n, _spread = weighted_primary_allowed(scored)
    pool, floor = eligible_pool(scored, require_semantic=True, max_size=3)
    top_one = conservative_choice(pool) if pool else current
    weights = (
        _effective_weights(
            pool,
            penalties=penalties or {},
            risk=risk,
            source=use_source,
            task_mode=use_mode,
        )
        if pool and rotate_ok
        else {}
    )
    if not rotate_ok:
        weighted = top_one
        weighted_note = reason
    elif len(pool) <= 1:
        weighted = pool[0] if pool else None
        weighted_note = "single_eligible"
    else:
        weighted = weighted_choice(pool, weights, rng_from_seed(use_seed + ":primary_geometry"))
        weighted_note = "weighted_eligible_pool"

    def _row(cand: ScoredCandidate | None) -> dict[str, Any] | None:
        if cand is None:
            return None
        return {
            "image_id": cand.image_id,
            "score": cand.score,
            "eligible": cand.eligible,
            "evidence_class": cand.verdict.evidence_class,
        }

    return {
        "selector_policy_version": SELECTOR_POLICY_VERSION,
        "seed": use_seed,
        "risk": risk,
        "pinned": {k: pinned.get(k) for k in (
            "product_id", "provider", "model", "aspect_ratio", "content_purpose", "quality_policy", "source", "task_mode"
        )},
        "quality_floor": floor,
        "weighted_rotation_enabled": rotate_ok,
        "weighted_rotation_disabled_reason": None if rotate_ok else reason,
        "C_note": weighted_note,
        "A_current_selector": _row(current),
        "B_quality_floor_top_one": _row(top_one),
        "C_quality_floor_weighted": _row(weighted),
        "metrics_template": {
            "product_fidelity": None,
            "geometry": None,
            "logo": None,
            "unsupported_invention": None,
            "realism": None,
            "composition_variety": None,
            "reference_reuse": None,
            "social_usefulness": None,
        },
        "note": "Manual local experiment only. Does not call paid providers.",
        "auto_provider_calls": False,
    }
