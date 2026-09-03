"""Controlled weighted reference selection. Reproducible from a stored seed."""

from __future__ import annotations

import hashlib
import random
import secrets
from dataclasses import dataclass, field
from typing import Any, Optional

from bebcare.models.generation_run import GenerationRun
from bebcare.models.product import ProductImage
from bebcare.schemas.reference_manifest import ReferenceManifest
from bebcare.services.quality_diversity_policy import (
    ABSOLUTE_MIN_SCORE,
    COOLDOWN_DECAY,
    COOLDOWN_FLOOR,
    FINGERPRINT_NEAR,
    FINGERPRINT_NEAR_FACTOR,
    FINGERPRINT_PARTIAL,
    FINGERPRINT_PARTIAL_FACTOR,
    LOOKBACK_RUNS,
    MAX_WEIGHTED_PRIMARY_POOL,
    MIN_ROLE_SCORE_SPREAD,
    MIN_USABLE_SEMANTIC_FOR_WEIGHTED_PRIMARY,
    NOVELTY_QUALITY_GAP,
    NOVELTY_WEIGHT_CAP,
    RELATIVE_BAND,
    SELECTOR_POLICY_VERSION,
    SEMANTIC_EVIDENCE_CLASSES,
    TEMPERATURE,
    CoverageClass,
    RiskBand,
    choose_shot_family,
    coverage_from_score,
    fingerprint_from_parts,
    quality_mix_for,
    role_absolute_min,
    scene_fingerprint_similarity,
)
from bebcare.services.quality_diversity_roles import RoleVerdict, evaluate_role
from bebcare.utils.reference_suitability import is_near_duplicate, suitability_score, tie_break_key

GEOMETRY_PRIMARY = "primary_geometry"
GEOMETRY_SUPPORT = "secondary_structure"


@dataclass
class ScoredCandidate:
    image: ProductImage
    verdict: RoleVerdict
    is_preferred: bool = False

    @property
    def image_id(self) -> str:
        return self.image.image_id

    @property
    def score(self) -> float:
        return self.verdict.score

    @property
    def eligible(self) -> bool:
        return self.verdict.eligible


@dataclass
class SelectorResult:
    selected: list[tuple[ProductImage, str, dict]]
    scene: tuple[ProductImage, str, dict] | None
    trace: dict
    coverage: CoverageClass
    risk: RiskBand
    seed: str
    diversity_applied: bool


def rng_from_seed(seed: str) -> random.Random:
    n = int(hashlib.sha256((seed or "").encode("utf-8")).hexdigest()[:16], 16)
    return random.Random(n)


def freeze_history_snapshot(history: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Replay identity includes this snapshot, not seed alone."""
    rows = list(history or [])
    run_ids = [str(row.get("run_id") or "") for row in rows if row.get("run_id")]
    return {
        "run_ids": run_ids,
        "cutoff_run_id": run_ids[0] if run_ids else None,
        "entry_count": len(rows),
        "entries": rows,
    }


def history_from_snapshot(snapshot: dict | list | None) -> list[dict[str, Any]]:
    if snapshot is None:
        return []
    if isinstance(snapshot, list):
        return list(snapshot)
    if isinstance(snapshot, dict):
        entries = snapshot.get("entries")
        if isinstance(entries, list):
            return list(entries)
    return []


def new_selection_seed() -> str:
    return secrets.token_hex(8)


def eligible_pool(
    scored: list[ScoredCandidate],
    *,
    absolute_min: float | None = None,
    relative_band: float = RELATIVE_BAND,
    require_semantic: bool = False,
    max_size: int | None = None,
    role: str | None = None,
) -> tuple[list[ScoredCandidate], dict]:
    if absolute_min is None:
        absolute_min = role_absolute_min(role or GEOMETRY_PRIMARY)
    eligible = [c for c in scored if c.eligible]
    excluded = [
        {"image_id": c.image_id, "reasons": list(c.verdict.exclusion_reasons), "score": c.score}
        for c in scored
        if not c.eligible
    ]
    if require_semantic:
        skipped = [c for c in eligible if c.verdict.evidence_class not in SEMANTIC_EVIDENCE_CLASSES]
        eligible = [c for c in eligible if c.verdict.evidence_class in SEMANTIC_EVIDENCE_CLASSES]
        excluded.extend(
            {"image_id": c.image_id, "reasons": ["resolution_only_not_role_suitable"], "score": c.score}
            for c in skipped
        )
    if not eligible:
        return [], {
            "absolute_min": absolute_min,
            "relative_band": relative_band,
            "best_score": None,
            "floor": absolute_min,
            "excluded": excluded,
            "eligible_ids": [],
            "require_semantic": require_semantic,
            "pool_cap": max_size,
        }
    best = max(c.score for c in eligible)
    floor = max(absolute_min, best - relative_band) if require_semantic else absolute_min
    if require_semantic:
        pool = [c for c in eligible if c.score >= floor]
        below = [
            {"image_id": c.image_id, "reasons": ["below_quality_floor"], "score": c.score}
            for c in eligible
            if c.score < floor
        ]
        excluded.extend(below)
    else:
        pool = list(eligible)
        floor = None
    pool = sorted(
        pool,
        key=lambda c: (
            -c.score,
            *tie_break_key(c.image.sort_index, c.image.uploaded_at, c.image.image_id),
        ),
    )
    clustered: list[ScoredCandidate] = []
    for cand in pool:
        if cand.is_preferred:
            clustered.append(cand)
            continue
        duplicate = False
        for kept in clustered:
            if is_near_duplicate(getattr(cand.image, "phash", None), getattr(kept.image, "phash", None)):
                duplicate = True
                excluded.append(
                    {"image_id": cand.image_id, "reasons": ["near_duplicate"], "score": cand.score}
                )
                break
        if not duplicate:
            clustered.append(cand)
    pool = clustered
    if max_size is not None and len(pool) > max_size:
        dropped = pool[max_size:]
        pool = pool[:max_size]
        excluded.extend(
            {"image_id": c.image_id, "reasons": ["above_pool_cap"], "score": c.score}
            for c in dropped
        )
    return pool, {
        "absolute_min": absolute_min,
        "relative_band": relative_band,
        "best_score": best,
        "floor": round(floor, 4) if floor is not None else None,
        "excluded": excluded,
        "eligible_ids": [c.image_id for c in pool],
        "require_semantic": require_semantic,
        "pool_cap": max_size,
    }


def _effective_weights(
    pool: list[ScoredCandidate],
    *,
    penalties: dict[str, float],
    risk: RiskBand,
    source: str,
    task_mode: str | None,
) -> dict[str, float]:
    temperature = TEMPERATURE[risk]
    mix = quality_mix_for(risk, source=source, task_mode=task_mode)
    raw: dict[str, float] = {}
    for cand in pool:
        quality = max(cand.score, 1e-6) ** temperature
        penalty = penalties.get(cand.image_id, 1.0)
        raw[cand.image_id] = mix * quality * penalty + (1.0 - mix) * 0.02 * penalty
    if len(pool) >= 2:
        ranked = sorted(pool, key=lambda c: c.score, reverse=True)
        best = ranked[0]
        for alt in ranked[1:]:
            if best.score - alt.score >= NOVELTY_QUALITY_GAP:
                cap = raw[best.image_id] * NOVELTY_WEIGHT_CAP
                if raw[alt.image_id] > cap:
                    raw[alt.image_id] = cap
    total = sum(raw.values()) or 1.0
    return {k: v / total for k, v in raw.items()}


def weighted_choice(
    pool: list[ScoredCandidate],
    weights: dict[str, float],
    rng: random.Random,
) -> ScoredCandidate:
    if not pool:
        raise RuntimeError("empty_eligible_pool")
    if len(pool) == 1:
        return pool[0]
    ordered = list(pool)
    w = [max(weights.get(c.image_id, 0.0), 0.0) for c in ordered]
    if sum(w) <= 0:
        return max(ordered, key=lambda c: (c.score, c.image_id))
    return rng.choices(ordered, weights=w, k=1)[0]


def conservative_choice(pool: list[ScoredCandidate]) -> ScoredCandidate:
    return sorted(
        pool,
        key=lambda c: (
            -c.score,
            *tie_break_key(c.image.sort_index, c.image.uploaded_at, c.image.image_id),
        ),
    )[0]


def phase1a_primary(
    images: list[ProductImage],
    *,
    intel_by_id: dict,
    repeats: dict[str, int],
    target_aspect: Optional[float],
    preferred: ProductImage | None,
) -> ProductImage | None:
    if preferred:
        return preferred
    valid = [img for img in images if img.cdn_url]
    if not valid:
        return None

    def rank_key(image: ProductImage):
        result = intel_by_id.get(image.image_id) if intel_by_id else None
        avoid = 0
        if result is not None and not image.is_preferred:
            if getattr(result, "is_packaging", lambda: False)() or getattr(
                result, "generation_suitability", ""
            ) == "avoid_as_primary":
                avoid = 1
        score = suitability_score(
            width=image.width,
            height=image.height,
            target_aspect=target_aspect,
            image_type=image.image_type or "product",
            primary_repeat_count=repeats.get(image.image_id, 0),
            apply_diversity=True,
        )
        return (
            avoid,
            -score,
            *tie_break_key(image.sort_index, image.uploaded_at, image.image_id),
        )

    return sorted(valid, key=rank_key)[0]


def weighted_primary_allowed(scored: list[ScoredCandidate]) -> tuple[bool, str, int, float]:
    semantic = [
        c
        for c in scored
        if c.eligible and c.verdict.evidence_class in SEMANTIC_EVIDENCE_CLASSES
    ]
    n = len(semantic)
    if n < MIN_USABLE_SEMANTIC_FOR_WEIGHTED_PRIMARY:
        return False, "insufficient_role_intelligence", n, 0.0
    scores = [c.score for c in semantic]
    spread = max(scores) - min(scores)
    if spread < MIN_ROLE_SCORE_SPREAD:
        return False, "nondiscriminating_role_scores", n, spread
    return True, "", n, spread


def cooldown_penalties(
    history: list[dict[str, Any]],
    *,
    preferred_id: str | None,
) -> dict[str, float]:
    counts: dict[str, float] = {}
    for index, row in enumerate(history):
        image_id = row.get("primary_reference_id") or row.get("image_id")
        if not image_id:
            continue
        decay = COOLDOWN_DECAY ** index
        counts[image_id] = counts.get(image_id, 0.0) + decay
        view = row.get("primary_view_class")
        combo = row.get("combination")
        if combo:
            counts[f"combo:{combo}"] = counts.get(f"combo:{combo}", 0.0) + 0.5 * decay
        if view:
            counts[f"view:{view}"] = counts.get(f"view:{view}", 0.0) + 0.25 * decay
    penalties: dict[str, float] = {}
    for image_id, weight in counts.items():
        if image_id.startswith("combo:") or image_id.startswith("view:"):
            continue
        factor = max(COOLDOWN_FLOOR, 1.0 - 0.22 * weight)
        if preferred_id and image_id == preferred_id:
            factor = max(factor, 0.92)
        penalties[image_id] = factor
    return penalties


def fingerprint_penalties(
    history: list[dict[str, Any]],
    proposed: dict[str, str],
    *,
    scene_only: bool = False,
) -> float:
    """Scene/composition similarity only. Do not apply a uniform factor to geometry ranking."""
    if not scene_only:
        return 1.0
    factor = 1.0
    for row in history:
        fp = row.get("fingerprint") or {}
        if not isinstance(fp, dict):
            continue
        sim = scene_fingerprint_similarity(fingerprint_from_parts(fp), proposed)
        if sim >= FINGERPRINT_NEAR:
            factor *= FINGERPRINT_NEAR_FACTOR
        elif sim >= FINGERPRINT_PARTIAL:
            factor *= FINGERPRINT_PARTIAL_FACTOR
    return max(COOLDOWN_FLOOR, factor)


def load_generation_history(
    session,
    *,
    product_id: str,
    owner_user_id: str,
    limit: int = LOOKBACK_RUNS,
) -> list[dict[str, Any]]:
    SUCCESS_STATUSES = frozenset({"succeeded", "success", "published", "selected"})
    rows = (
        session.query(GenerationRun)
        .filter(
            GenerationRun.product_id == product_id,
            GenerationRun.owner_user_id == owner_user_id,
            GenerationRun.status.in_(tuple(SUCCESS_STATUSES)),
        )
        .order_by(GenerationRun.created_at.desc(), GenerationRun.run_id.desc())
        .limit(limit * 2)
        .all()
    )
    history: list[dict[str, Any]] = []
    for run in rows:
        if run.fallback_path or run.fallback_reason:
            continue
        if (run.executed_selector_strategy or "") == "selector_fallback":
            continue
        plan = run.generation_plan if isinstance(run.generation_plan, dict) else {}
        fp = plan.get("diversity_fingerprint") if isinstance(plan.get("diversity_fingerprint"), dict) else {}
        manifest_raw = run.reference_manifest
        primary = None
        combo = []
        view = ""
        try:
            manifest = ReferenceManifest.model_validate(manifest_raw) if manifest_raw else None
        except Exception:
            manifest = None
        if manifest:
            primary = manifest.primary_image_id()
            combo = [item.image_id for item in manifest.items if item.image_id]
        if isinstance(plan.get("selector_trace"), dict):
            view = str((plan["selector_trace"].get("primary_view_class") or ""))
        history.append(
            {
                "run_id": run.run_id,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "primary_reference_id": fp.get("primary_reference_id") or primary,
                "primary_view_class": fp.get("primary_view_class") or view,
                "combination": "|".join(combo),
                "fingerprint": fp or {
                    "primary_reference_id": primary or "",
                    "aspect_ratio": str(run.image_size or ""),
                },
                "source": run.source,
            }
        )
    return history[:limit]


def score_images(
    images: list[ProductImage],
    *,
    role: str,
    intel_by_id: dict,
    target_aspect: Optional[float],
    intended_component: str | None = None,
    packaging_required: bool = False,
) -> list[ScoredCandidate]:
    scored: list[ScoredCandidate] = []
    for image in images:
        intel = intel_by_id.get(image.image_id) if intel_by_id else None
        verdict = evaluate_role(
            role,
            width=image.width,
            height=image.height,
            image_type=image.image_type,
            intel=intel,
            target_aspect=target_aspect,
            intended_component=intended_component,
            packaging_required=packaging_required,
            analysis_status=getattr(image, "analysis_status", None),
        )
        scored.append(
            ScoredCandidate(image=image, verdict=verdict, is_preferred=bool(image.is_preferred))
        )
    return scored


def _geometry_pool_observability(
    scored: list[ScoredCandidate],
    *,
    history: list[dict[str, Any]],
    preferred: ProductImage | None,
    risk: RiskBand,
    source: str,
    task_mode: str | None,
) -> tuple[list[ScoredCandidate], dict, dict[str, float], dict[str, float]]:
    pool, floor_info = eligible_pool(
        scored,
        require_semantic=True,
        max_size=MAX_WEIGHTED_PRIMARY_POOL,
        role=GEOMETRY_PRIMARY,
    )
    penalties = cooldown_penalties(history, preferred_id=preferred.image_id if preferred else None)
    weights = (
        _effective_weights(pool, penalties=penalties, risk=risk, source=source, task_mode=task_mode)
        if pool
        else {}
    )
    return pool, floor_info, penalties, weights


def select_weighted(
    images: list[ProductImage],
    *,
    role: str,
    intel_by_id: dict,
    target_aspect: Optional[float],
    seed: str,
    risk: RiskBand,
    source: str,
    task_mode: str | None,
    history: list[dict[str, Any]],
    preferred: ProductImage | None = None,
    exclude_ids: set[str] | None = None,
    exclude_near: ProductImage | None = None,
    intended_component: str | None = None,
    packaging_required: bool = False,
    fingerprint_parts: dict[str, str] | None = None,
    force_top_one: bool = False,
    require_semantic: bool | None = None,
) -> tuple[ScoredCandidate | None, dict]:
    pool_images = []
    for image in images:
        if exclude_ids and image.image_id in exclude_ids:
            continue
        if exclude_near and image.image_id != exclude_near.image_id:
            if is_near_duplicate(exclude_near.phash, image.phash):
                continue
        pool_images.append(image)
    scored = score_images(
        pool_images,
        role=role,
        intel_by_id=intel_by_id,
        target_aspect=target_aspect,
        intended_component=intended_component,
        packaging_required=packaging_required,
    )
    raw_scores = {c.image_id: {"score": c.score, "eligible": c.eligible, "reasons": c.verdict.exclusion_reasons, "signals": c.verdict.signals} for c in scored}
    preferred_id = preferred.image_id if preferred else None
    if require_semantic is None:
        require_semantic = (role == GEOMETRY_PRIMARY and not force_top_one) or role == GEOMETRY_SUPPORT
    cap = MAX_WEIGHTED_PRIMARY_POOL if role == GEOMETRY_PRIMARY and require_semantic else None
    pool, floor_info = eligible_pool(
        scored,
        require_semantic=require_semantic,
        max_size=cap,
        role=role,
        absolute_min=role_absolute_min(role),
    )
    preferred_forced = False
    if preferred and any(c.image_id == preferred.image_id for c in scored):
        pref_scored = next(c for c in scored if c.image_id == preferred.image_id)
        preferred_forced = True
        pool = [pref_scored]
    penalties = cooldown_penalties(history, preferred_id=preferred_id)
    scene_fp = role == "scene_reference"
    fp_factor = fingerprint_penalties(
        history, fingerprint_from_parts(fingerprint_parts), scene_only=scene_fp
    )
    if scene_fp:
        for cand in pool:
            penalties[cand.image_id] = penalties.get(cand.image_id, 1.0) * fp_factor
    for cand in pool:
        if preferred_id and cand.image_id == preferred_id:
            penalties[cand.image_id] = max(penalties.get(cand.image_id, 1.0), 0.92)
    weights = _effective_weights(pool, penalties=penalties, risk=risk, source=source, task_mode=task_mode) if pool else {}
    chosen: ScoredCandidate | None = None
    diversity_applied = False
    reason = "empty"
    if pool:
        conservative = risk == "conservative" or force_top_one
        if preferred_forced:
            chosen = pool[0]
            reason = "preferred_authority"
        elif conservative or len(pool) == 1:
            chosen = conservative_choice(pool)
            if len(pool) == 1:
                reason = "intentional_reuse" if history else "single_eligible"
            else:
                reason = "conservative_top"
        else:
            chosen = weighted_choice(pool, weights, rng_from_seed(seed + ":" + role))
            diversity_applied = chosen.image_id != conservative_choice(pool).image_id
            reason = "weighted_eligible_pool"
    trace = {
        "role": role,
        "raw_scores": raw_scores,
        "quality_floor": floor_info,
        "diversity_penalties": penalties,
        "effective_weights": weights,
        "selected_id": chosen.image_id if chosen else None,
        "selection_reason": reason,
        "diversity_applied": diversity_applied,
        "fingerprint_factor": fp_factor,
    }
    return chosen, trace


def run_grounded_quality_diversity(
    *,
    products: list[ProductImage],
    scenes: list[ProductImage],
    intel_by_id: dict,
    target_aspect: Optional[float],
    count: int,
    use_scene: bool,
    seed: str,
    source: str,
    task_mode: str | None,
    history: list[dict[str, Any]],
    risk_hint: dict[str, Any] | None = None,
    intended_component: str | None = None,
    packaging_required: bool = False,
    repeats: dict[str, int] | None = None,
    explicit_pins: list[ProductImage] | None = None,
) -> SelectorResult:
    from bebcare.services.quality_diversity_policy import resolve_risk_band

    hint = risk_hint or {}
    repeats = repeats or {}
    products = [
        img for img in products if (getattr(img, "image_type", None) or "product") != "scene"
    ]
    preferred = next((img for img in products if img.is_preferred), None)
    pin_primary = (explicit_pins or [None])[0]
    primary_scores = score_images(
        products,
        role=GEOMETRY_PRIMARY,
        intel_by_id=intel_by_id,
        target_aspect=target_aspect,
        intended_component=intended_component,
        packaging_required=packaging_required,
    )
    rotate_ok, rotate_block, usable_n, spread = weighted_primary_allowed(primary_scores)
    intel_classes = {
        c.image_id: c.verdict.evidence_class for c in primary_scores
    }
    availability = "usable" if rotate_ok else (rotate_block or "insufficient_role_intelligence")
    best_eligible = max((c.score for c in primary_scores if c.eligible), default=0.0)
    pref_verdict = next((c.verdict for c in primary_scores if preferred and c.image_id == preferred.image_id), None)
    pin_verdict = next((c.verdict for c in primary_scores if pin_primary and c.image_id == pin_primary.image_id), None)
    score_for_cov = best_eligible
    if pref_verdict:
        score_for_cov = pref_verdict.score
    if pin_verdict:
        score_for_cov = pin_verdict.score
    coverage = coverage_from_score(
        score_for_cov,
        eligible=True if (pin_primary or preferred) else any(c.eligible for c in primary_scores),
    )
    if preferred and pref_verdict and not pref_verdict.eligible:
        coverage = "limited"
    if pin_primary and pin_verdict and not pin_verdict.eligible:
        coverage = "limited"
    if rotate_block == "insufficient_role_intelligence":
        coverage = "limited"
    risk, risk_reasons = resolve_risk_band(
        source=source,
        task_mode=task_mode,
        coverage=coverage,
        capture_style=hint.get("capture_style"),
        offering_kind=hint.get("offering_kind"),
        dimension_text=str(hint.get("dimension_text") or ""),
        content_purpose=hint.get("content_purpose"),
        camera_distance=hint.get("camera_distance"),
        explore_requested=bool(hint.get("explore_requested")),
        auto_publish=bool(hint.get("auto_publish")),
        logo_fidelity_required=bool(hint.get("logo_fidelity_required")),
        screenshot_risk=bool(hint.get("screenshot_risk")),
        transparent_risk=bool(hint.get("transparent_risk")),
        display_risk=bool(hint.get("display_risk")),
        close_up_risk=bool(hint.get("close_up_risk")),
        safety_placement_risk=bool(hint.get("safety_placement_risk")),
        insufficient_role_intelligence=not rotate_ok,
    )
    shot_family = choose_shot_family(
        coverage=coverage,
        risk=risk,
        capture_style=hint.get("capture_style"),
        offering_kind=hint.get("offering_kind"),
        history=history,
        seed=seed,
        auto_publish=bool(hint.get("auto_publish")),
    )
    fp_parts = fingerprint_from_parts(
        {
            "content_purpose": hint.get("content_purpose"),
            "capture_style": hint.get("capture_style"),
            "camera_distance": hint.get("camera_distance"),
            "aspect_ratio": hint.get("aspect_ratio"),
            "display_configuration": hint.get("display_configuration"),
            "scene_family": hint.get("scene_family") or hint.get("dimension_text"),
            "shot_family": shot_family,
        }
    )
    selected: list[tuple[ProductImage, str, dict]] = []
    traces: list[dict] = []
    force_primary_top = (not rotate_ok) or risk == "conservative"
    if pin_primary is not None:
        primary = next((c for c in primary_scores if c.image_id == pin_primary.image_id), None)
        if primary is None:
            primary = ScoredCandidate(
                image=pin_primary,
                verdict=evaluate_role(
                    GEOMETRY_PRIMARY,
                    width=pin_primary.width,
                    height=pin_primary.height,
                    image_type=pin_primary.image_type,
                    intel=(intel_by_id or {}).get(pin_primary.image_id),
                    analysis_status=getattr(pin_primary, "analysis_status", None),
                ),
                is_preferred=bool(pin_primary.is_preferred),
            )
        _, floor_info, penalties, weights = _geometry_pool_observability(
            primary_scores,
            history=history,
            preferred=preferred,
            risk=risk,
            source=source,
            task_mode=task_mode,
        )
        primary_trace = {
            "role": GEOMETRY_PRIMARY,
            "selection_reason": "explicit_pin",
            "diversity_applied": False,
            "weighted_rotation_enabled": False,
            "weighted_rotation_disabled_reason": "explicit_pin",
            "quality_floor": floor_info,
            "effective_weights": weights,
            "diversity_penalties": penalties,
            "raw_scores": {
                c.image_id: {
                    "score": c.score,
                    "eligible": c.eligible,
                    "reasons": c.verdict.exclusion_reasons,
                    "evidence_class": c.verdict.evidence_class,
                }
                for c in primary_scores
            },
        }
    elif force_primary_top:
        picked_img = phase1a_primary(
            products,
            intel_by_id=intel_by_id,
            repeats=repeats,
            target_aspect=target_aspect,
            preferred=preferred,
        )
        if picked_img is None:
            raise RuntimeError("no_valid_product_references")
        primary = next((c for c in primary_scores if c.image_id == picked_img.image_id), None)
        if primary is None:
            primary = ScoredCandidate(
                image=picked_img,
                verdict=evaluate_role(
                    GEOMETRY_PRIMARY,
                    width=picked_img.width,
                    height=picked_img.height,
                    image_type=picked_img.image_type,
                    intel=(intel_by_id or {}).get(picked_img.image_id),
                    analysis_status=getattr(picked_img, "analysis_status", None),
                ),
                is_preferred=bool(picked_img.is_preferred),
            )
        _, floor_info, penalties, weights = _geometry_pool_observability(
            primary_scores,
            history=history,
            preferred=preferred,
            risk=risk,
            source=source,
            task_mode=task_mode,
        )
        primary_trace = {
            "role": GEOMETRY_PRIMARY,
            "selection_reason": "preferred_authority" if preferred and primary.image_id == preferred.image_id else "conservative_top",
            "diversity_applied": False,
            "weighted_rotation_enabled": False,
            "weighted_rotation_disabled_reason": rotate_block or ("conservative_risk" if risk == "conservative" else None),
            "quality_floor": floor_info,
            "effective_weights": weights,
            "diversity_penalties": penalties,
            "raw_scores": {
                c.image_id: {
                    "score": c.score,
                    "eligible": c.eligible,
                    "reasons": c.verdict.exclusion_reasons,
                    "evidence_class": c.verdict.evidence_class,
                }
                for c in primary_scores
            },
        }
    else:
        primary, primary_trace = select_weighted(
            products,
            role=GEOMETRY_PRIMARY,
            intel_by_id=intel_by_id,
            target_aspect=target_aspect,
            seed=seed,
            risk=risk,
            source=source,
            task_mode=task_mode,
            history=history,
            preferred=preferred,
            intended_component=intended_component,
            packaging_required=packaging_required,
            fingerprint_parts=fp_parts,
        )
        primary_trace["weighted_rotation_enabled"] = True
        primary_trace["weighted_rotation_disabled_reason"] = None
    traces.append(primary_trace)
    if primary is None and primary_scores:
        primary = max(primary_scores, key=lambda c: (c.score, c.image_id))
        coverage = "insufficient"
        primary_trace["selection_reason"] = "insufficient_fallback"
    if primary is None:
        raise RuntimeError("no_valid_product_references")
    if pin_primary and primary.image_id == pin_primary.image_id:
        authority = "explicit_pin"
    elif preferred and primary.image_id == preferred.image_id:
        authority = "preferred"
    else:
        authority = "suitability"
    selected.append(
        (
            primary.image,
            authority,
            {
                "score": primary.score,
                "role": GEOMETRY_PRIMARY,
                "coverage": coverage,
                "selector": SELECTOR_POLICY_VERSION,
            },
        )
    )
    remaining = [img for img in products if img.image_id != primary.image_id]
    support_slots = max(int(count or 1), 1)
    for extra in (explicit_pins or [])[1:]:
        if len(selected) >= support_slots:
            break
        if extra.image_id == primary.image_id:
            continue
        selected.append(
            (
                extra,
                "explicit_pin",
                {"score": None, "role": GEOMETRY_SUPPORT, "selector": SELECTOR_POLICY_VERSION},
            )
        )
        remaining = [img for img in remaining if img.image_id != extra.image_id]
    primary_view = str((primary.verdict.signals or {}).get("view_class") or "")
    while len(selected) < support_slots and remaining:
        nxt, tr = select_weighted(
            remaining,
            role=GEOMETRY_SUPPORT,
            intel_by_id=intel_by_id,
            target_aspect=target_aspect,
            seed=seed + f":support:{len(selected)}",
            risk=risk,
            source=source,
            task_mode=task_mode,
            history=history,
            preferred=None,
            exclude_near=primary.image,
            intended_component=intended_component,
            packaging_required=packaging_required,
            fingerprint_parts=fp_parts,
            force_top_one=True,
            require_semantic=True,
        )
        traces.append(tr)
        if nxt is None:
            break
        nxt_view = str((nxt.verdict.signals or {}).get("view_class") or "")
        same_view = (
            primary_view
            and nxt_view
            and primary_view not in ("unknown", "")
            and nxt_view == primary_view
        )
        has_other_view = any(
            str(
                (
                    evaluate_role(
                        GEOMETRY_SUPPORT,
                        width=img.width,
                        height=img.height,
                        image_type=img.image_type,
                        intel=(intel_by_id or {}).get(img.image_id),
                    ).signals
                    or {}
                ).get("view_class")
                or ""
            )
            not in ("", "unknown", primary_view)
            for img in remaining
            if img.image_id != nxt.image_id
        )
        if same_view and primary.eligible and has_other_view:
            remaining = [img for img in remaining if img.image_id != nxt.image_id]
            continue
        selected.append(
            (
                nxt.image,
                "suitability",
                {"score": nxt.score, "role": GEOMETRY_SUPPORT, "selector": SELECTOR_POLICY_VERSION},
            )
        )
        remaining = [img for img in remaining if img.image_id != nxt.image_id]
    scene_choice = None
    if use_scene and scenes:
        scene_pref = next((img for img in scenes if img.is_preferred), None)
        scene_risk: RiskBand = "balanced" if not rotate_ok else risk
        scene_cand, scene_tr = select_weighted(
            scenes,
            role="scene_reference",
            intel_by_id=intel_by_id,
            target_aspect=target_aspect,
            seed=seed + ":scene",
            risk=scene_risk,
            source=source,
            task_mode=task_mode,
            history=history,
            preferred=scene_pref,
            fingerprint_parts=fp_parts,
            force_top_one=False,
        )
        traces.append(scene_tr)
        if scene_cand:
            scene_choice = (
                scene_cand.image,
                "preferred" if scene_pref and scene_cand.image_id == scene_pref.image_id else "suitability",
                {"score": scene_cand.score, "role": "scene_reference"},
            )
    view = ""
    intel = intel_by_id.get(primary.image_id) if intel_by_id else None
    if intel is not None:
        physical = getattr(intel, "physical", None)
        if physical is not None:
            view = str(getattr(physical, "broad_view_class", "") or "")
        elif isinstance(intel, dict):
            view = str(((intel.get("physical") or {}).get("broad_view_class")) or "")
    fp_parts["primary_reference_id"] = primary.image_id
    fp_parts["primary_view_class"] = view
    diversity_applied = any(t.get("diversity_applied") for t in traces)
    weighted_on = bool(primary_trace.get("weighted_rotation_enabled"))
    trace = {
        "selector_policy_version": SELECTOR_POLICY_VERSION,
        "selection_seed": seed,
        "risk_band": risk,
        "risk_reasons": risk_reasons,
        "coverage": coverage,
        "intelligence_availability": availability,
        "intelligence_confidence_class": availability,
        "intelligence_by_image": intel_classes,
        "usable_semantic_count": usable_n,
        "role_score_spread": round(spread, 4),
        "weighted_rotation_enabled": weighted_on,
        "weighted_rotation_disabled_reason": primary_trace.get("weighted_rotation_disabled_reason"),
        "eligible_candidate_ids": (primary_trace.get("quality_floor") or {}).get("eligible_ids") or [],
        "raw_role_scores": {t.get("role"): t.get("raw_scores") for t in traces},
        "quality_floor": primary_trace.get("quality_floor"),
        "relative_window": RELATIVE_BAND,
        "pool_cap": MAX_WEIGHTED_PRIMARY_POOL,
        "diversity_penalties": primary_trace.get("diversity_penalties"),
        "effective_weights": primary_trace.get("effective_weights"),
        "selected_ids": [img.image_id for img, _a, _m in selected],
        "exclusion_reasons": (primary_trace.get("quality_floor") or {}).get("excluded") or [],
        "selection_reason": primary_trace.get("selection_reason"),
        "diversity_applied": diversity_applied,
        "primary_view_class": view,
        "shot_family": shot_family,
        "fingerprint": fp_parts,
        "intentional_reuse": primary_trace.get("selection_reason") == "intentional_reuse",
        "history_snapshot": freeze_history_snapshot(history),
        "steps": traces,
        "preferred_limited": bool(preferred and pref_verdict and not pref_verdict.eligible),
        "selector_context": {k: hint.get(k) for k in (
            "auto_publish", "close_up_risk", "logo_fidelity_required",
            "offering_kind", "content_purpose",
        )},
    }
    return SelectorResult(
        selected=selected,
        scene=scene_choice,
        trace=trace,
        coverage=coverage,
        risk=risk,
        seed=seed,
        diversity_applied=diversity_applied,
    )
