"""Final pass: remove leftover prompt instructions that contradict applied protections.

Does not call image models. Does not store the full prompt. Persistence is best-effort.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from bebcare.services.grounded_rollout import SOURCE_STUDIO
from bebcare.services.product_fidelity_rollout import prevention_enabled

logger = logging.getLogger(__name__)

POLICY_NAME = "prompt_contradiction_guard"
POLICY_VERSION = "prompt_contradiction_guard_v1"

PROHIBITION_RE = re.compile(
    r"\b(do not|don't|dont|never|avoid|prohibit|prohibited|must not|forbidden|"
    r"禁止|不要|勿)\b",
    re.IGNORECASE,
)

# Positive leftover requests. Prohibition sentences that mention the same topic are kept.
HANDHELD_REQUEST_RE = re.compile(
    r"hand-?held replacement|use hand-held replacement|"
    r"replace the product in (?:their|the|a) hands?|"
    r"swap the product in (?:their|the) hands?|"
    r"fingers must contact the product|"
    r"keep grip, arm pose|"
    r"手持替换|把手中的产品换",
    re.IGNORECASE,
)

CLOSEUP_REQUEST_RE = re.compile(
    r"\b(?:extreme\s+)?(?:macro shot|macro hero|tight crop|dutch angle|worm'?s eye|bird'?s eye)\b|"
    r"\bextreme close-?up\b|\bhero close-?up\b|\bproduct close-?up hero\b",
    re.IGNORECASE,
)

BRANDING_REQUEST_RE = re.compile(
    r"preserve visible branding(?!=False)|"
    r"copy the logo(?: region)?|"
    r"recreate the (?:wordmark|logo|brand mark)|"
    r"the exact case-sensitive wordmark|"
    r"Logo placement must be copied|"
    r"保留可见品牌(?!关系关闭)",
    re.IGNORECASE,
)

BRANDING_CONTRACT_RE = re.compile(
    r"Preserve identity-defining structure, proportions, branding, and visible relationships\.",
    re.IGNORECASE,
)

BRANDING_FLAG_RE = re.compile(r"preserve visible branding=True", re.IGNORECASE)

IMAGE_ZERO_RE = re.compile(r"\bImage 0\b")

FLOATING_PRODUCT_RE = re.compile(
    r"\bfloating product\b|\bproduct floating in (?:mid-?)?air\b|\b悬空产品\b",
    re.IGNORECASE,
)

VARIETY_VS_COVERAGE_RE = re.compile(
    r"vary scene family, lighting, and palette",
    re.IGNORECASE,
)

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。；;])\s+")


def _source(info: dict) -> str:
    return (
        (info.get("generation_provenance") or {}).get("source")
        or info.get("source")
        or SOURCE_STUDIO
    )


def _plan(info: dict) -> dict[str, Any]:
    raw = info.get("generation_plan")
    return raw if isinstance(raw, dict) else {}


def _logo(plan: dict) -> dict[str, Any]:
    logo = plan.get("logo_policy")
    if isinstance(logo, dict):
        return logo
    nested = plan.get("fidelity")
    if isinstance(nested, dict) and isinstance(nested.get("logo"), dict):
        return nested["logo"]
    return {}


def guard_applies(product_info: dict | None) -> bool:
    info = product_info or {}
    plan = _plan(info)
    if plan:
        return True
    return prevention_enabled(source=_source(info))


def _handheld_prohibited(plan: dict) -> bool:
    if not plan:
        return False
    return str(plan.get("handheld_physical_replacement") or "prohibited") == "prohibited"


def _branding_withheld(plan: dict, info: dict) -> bool:
    logo = _logo(plan)
    if logo.get("generated_branding_prohibited") is True:
        return True
    if logo.get("insert_wordmark_in_prompt") is False:
        return True
    overlay = info.get("fidelity_guard") if isinstance(info.get("fidelity_guard"), dict) else {}
    nested = overlay.get("logo_policy") if isinstance(overlay.get("logo_policy"), dict) else {}
    return bool(nested.get("generated_branding_prohibited")) or nested.get("insert_wordmark_in_prompt") is False


def _coverage_restricted(plan: dict) -> bool:
    coverage = str(plan.get("reference_coverage") or "")
    constraints = plan.get("coverage_constraints") or []
    extra = plan.get("extra_constraints") or []
    if coverage in ("limited", "insufficient"):
        return True
    blob = " ".join(str(x) for x in list(constraints) + list(extra))
    return "no_macro" in blob or "no_handheld" in blob or "coverage_limited" in blob


def _placement_simplified(plan: dict) -> bool:
    placement = plan.get("placement") if isinstance(plan.get("placement"), dict) else {}
    simplifications = plan.get("fidelity_simplifications") or []
    extra = plan.get("extra_constraints") or []
    if placement.get("simplified_from"):
        return True
    joined = " ".join(str(x) for x in list(simplifications) + list(extra))
    return "unsupported" in joined or "stable_surface" in joined or "vague_mount" in joined


def _drop_request_sentences(text: str, pattern: re.Pattern[str]) -> tuple[str, bool]:
    if not text or not pattern.search(text):
        return text, False
    parts = SENTENCE_SPLIT_RE.split(text)
    kept: list[str] = []
    changed = False
    for part in parts:
        chunk = part.strip()
        if not chunk:
            continue
        if pattern.search(chunk) and not PROHIBITION_RE.search(chunk):
            changed = True
            continue
        kept.append(chunk)
    if not changed:
        return text, False
    rebuilt = " ".join(kept)
    rebuilt = re.sub(r"\s+", " ", rebuilt).strip()
    return rebuilt, True


def apply_prompt_contradiction_guard(prompt: str, product_info: dict | None) -> tuple[str, dict[str, Any]]:
    """Rewrite leftover contradictory requests. Never returns secrets or the raw prompt in the report."""
    info = product_info if isinstance(product_info, dict) else {}
    text = prompt or ""
    empty = {
        "policy_version": POLICY_VERSION,
        "evaluated": False,
        "applied": False,
        "resolved": [],
    }
    if not guard_applies(info):
        return text.strip(), empty
    plan = _plan(info)
    resolved: list[str] = []
    if _handheld_prohibited(plan):
        text, changed = _drop_request_sentences(text, HANDHELD_REQUEST_RE)
        if changed:
            resolved.append("handheld_request_removed")
    if _coverage_restricted(plan):
        text, changed = _drop_request_sentences(text, CLOSEUP_REQUEST_RE)
        if changed:
            resolved.append("coverage_viewpoint_restricted")
        if VARIETY_VS_COVERAGE_RE.search(text) and not PROHIBITION_RE.search(
            next((s for s in SENTENCE_SPLIT_RE.split(text) if VARIETY_VS_COVERAGE_RE.search(s)), "")
        ):
            text, variety_changed = _drop_request_sentences(text, VARIETY_VS_COVERAGE_RE)
            if variety_changed:
                resolved.append("coverage_over_variety")
        from bebcare.services.quality_diversity_policy import coverage_prompt

        extra = coverage_prompt(str(plan.get("reference_coverage") or "limited"))  # type: ignore[arg-type]
        if extra and extra.lower() not in text.lower():
            text = f"{text} {extra}".strip()
            if "coverage_constraints_applied" not in resolved:
                resolved.append("coverage_constraints_applied")
    if _branding_withheld(plan, info):
        if BRANDING_CONTRACT_RE.search(text):
            text = BRANDING_CONTRACT_RE.sub(
                "Preserve identity-defining structure, proportions, and visible relationships. "
                "Do not generate branding.",
                text,
            )
            resolved.append("branding_contract_aligned")
        if BRANDING_FLAG_RE.search(text):
            text = BRANDING_FLAG_RE.sub("preserve visible branding=False", text)
            resolved.append("branding_flag_aligned")
        text, changed = _drop_request_sentences(text, BRANDING_REQUEST_RE)
        if changed:
            resolved.append("generated_branding_request_removed")
    if _placement_simplified(plan) or _coverage_restricted(plan):
        text, changed = _drop_request_sentences(text, FLOATING_PRODUCT_RE)
        if changed:
            resolved.append("stable_surface_enforced")
            if "resting on a stable surface" not in text.lower():
                text = f"{text} Place the product fully on a stable dresser, shelf, table, or counter.".strip()
    if IMAGE_ZERO_RE.search(text):
        text = IMAGE_ZERO_RE.sub("Image 1", text)
        resolved.append("image_index_corrected")
    resolved = list(dict.fromkeys(resolved))
    report = {
        "policy_version": POLICY_VERSION,
        "evaluated": True,
        "applied": bool(resolved),
        "resolved": resolved,
    }
    if isinstance(info.get("generation_plan"), dict):
        info["generation_plan"]["prompt_contradiction"] = report
    provenance = info.setdefault("generation_provenance", {})
    if isinstance(provenance, dict):
        provenance["prompt_contradiction"] = report
    logger.info(
        "generation_diagnostics",
        extra={
            "generation_run_id": info.get("generation_run_id"),
            "event": "prompt_contradiction_resolved" if resolved else "prompt_contradiction_evaluated",
            "stage": "pre_provider",
            "outcome": "applied" if resolved else "clean",
            "policy_version": POLICY_VERSION,
            "product_id": info.get("product_id"),
            "artifact_index": None,
            "error_category": None,
            "resolved": resolved,
        },
    )
    return text.strip(), report


def persist_prompt_contradiction(db: Any, product_info: dict | None) -> None:
    """Best-effort event + plan merge. Must not raise to the generation caller."""
    info = product_info or {}
    run_id = info.get("generation_run_id")
    report = None
    plan = info.get("generation_plan")
    if isinstance(plan, dict) and isinstance(plan.get("prompt_contradiction"), dict):
        report = plan["prompt_contradiction"]
    provenance = info.get("generation_provenance") if isinstance(info.get("generation_provenance"), dict) else {}
    if report is None and isinstance(provenance.get("prompt_contradiction"), dict):
        report = provenance["prompt_contradiction"]
    if not run_id or not report or not report.get("evaluated"):
        return
    try:
        from bebcare.models.generation_qds import GenerationDecisionEvent
        from bebcare.models.generation_run import GenerationRun
        from bebcare.services.ownership import stamp_owner
        from bebcare.services.quality_diversity_events import _safe_details

        run = db.query(GenerationRun).filter(GenerationRun.run_id == str(run_id)).first()
        if run is None:
            return
        if run.owner_user_id and info.get("owner_user_id") and run.owner_user_id != info.get("owner_user_id"):
            return
        nested = db.begin_nested()
        stored = run.generation_plan if isinstance(run.generation_plan, dict) else {}
        merged = dict(stored)
        if isinstance(plan, dict):
            merged.update({k: v for k, v in plan.items() if k != "prompt"})
        merged["prompt_contradiction"] = {
            "policy_version": report.get("policy_version"),
            "evaluated": True,
            "applied": bool(report.get("applied")),
            "resolved": list(report.get("resolved") or [])[:12],
        }
        run.generation_plan = merged
        existing = (
            db.query(GenerationDecisionEvent)
            .filter(
                GenerationDecisionEvent.generation_run_id == run.run_id,
                GenerationDecisionEvent.event_type.in_(
                    ("prompt_contradiction_resolved", "prompt_contradiction_evaluated")
                ),
            )
            .first()
        )
        if existing is None:
            max_seq = (
                db.query(GenerationDecisionEvent.sequence_number)
                .filter(GenerationDecisionEvent.generation_run_id == run.run_id)
                .order_by(GenerationDecisionEvent.sequence_number.desc())
                .first()
            )
            sequence = int(max_seq[0]) + 1 if max_seq else 0
            applied = bool(report.get("applied"))
            rec = GenerationDecisionEvent(
                generation_run_id=run.run_id,
                sequence_number=sequence,
                event_type="prompt_contradiction_resolved" if applied else "prompt_contradiction_evaluated",
                stage="pre_provider",
                outcome="applied" if applied else "clean",
                severity="info",
                policy_name=POLICY_NAME,
                policy_version=POLICY_VERSION,
                summary="Conflicting prompt instructions removed" if applied else "Final prompt checked for contradictions",
                details=_safe_details({"resolved": list(report.get("resolved") or [])[:12]}),
            )
            stamp_owner(rec, type("Owner", (), {"user_id": run.owner_user_id})())
            db.add(rec)
        nested.commit()
    except Exception:
        logger.warning(
            "prompt_contradiction_persist_failed",
            extra={
                "generation_run_id": run_id,
                "event": "prompt_contradiction_persist_failed",
                "stage": "pre_provider",
                "outcome": "error",
                "policy_version": POLICY_VERSION,
                "product_id": info.get("product_id"),
                "error_category": "observability_persist",
            },
        )
