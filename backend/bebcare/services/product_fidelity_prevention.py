"""Checkpoint A: pre-generation product fidelity protection. No extra image-model calls."""

from __future__ import annotations

import re
from typing import Any, Iterable

from bebcare.schemas.generation_plan import NON_PHYSICAL_OFFERING_KINDS, PHYSICAL_OFFERING_KINDS
from bebcare.services.grounded_rollout import SOURCE_STUDIO
from bebcare.services.product_fidelity_rollout import (
    PREVENTION_POLICY_VERSION,
    prevention_enabled,
    product_fidelity_prevention_mode,
)

RENDER_RE = re.compile(
    r"\bc4d\b|cinema\s*4d|octane\s*render|blender\s*render|unreal\s*engine\s*render|"
    r"\b3d\s*render\b|cgi(?:\s+product)?\s*render|cgi\s+render|"
    r"perfect\s*ray[-\s]*traced|protective\s*halo|magical\s*(?:product\s*)?(?:glow|light)|"
    r"\b8k\b|\bpristine\b|\bflawless\b|"
    r"dreamy\s*airy\s*bokeh|high[-\s]*end\s*e[-\s]*commerce|meticulous\s*rendering|"
    r"perfect\s*diffused\s*lighting",
    re.IGNORECASE,
)

FLOATING_SYMBOL_RE = re.compile(
    r"\bfloating\s+(?:icons?|symbols?|hearts?|sparkles?|badges?|pictograms?)\b",
    re.IGNORECASE,
)

PHOTOGRAPHIC_CONTRACT = (
    "naturally captured lifestyle photograph; contemporary smartphone or editorial-camera "
    "perspective; moderate depth of field; ordinary lens and sensor imperfections; "
    "restrained highlights; environment-specific reflections; scene-consistent grain, "
    "sharpness, exposure, and white balance; real molded-plastic, metal, glass, fabric, "
    "or screen behavior; no synthetic render finish"
)

# Phrase-level physical installation only. Isolated verbs/nouns (stands, clip, case) are not matches.
UNSUPPORTED_INSTALL_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        r"crib[-\s]?rail|side\s+rail\s+of\s+(?:a\s+)?(?:\w+\s+)?crib|"
        r"mounted\s+on\s+(?:the\s+)?(?:side\s+)?rail(?:\s+of\s+(?:a\s+)?(?:\w+\s+)?crib)?",
        "crib_rail_mount",
    ),
    (
        r"wall[-\s]?mount(?:ed|ing)?|fixed\s+to\s+a\s+wall|mounted\s+on\s+(?:the\s+)?wall",
        "wall_mount",
    ),
    (
        r"clip(?:ped)?\s+to\s+(?:the\s+)?crib|clip\s+mount|attached\s+(?:with|using)\s+"
        r"(?:an?\s+)?(?:unsupported\s+)?clip(?:\s+mount)?",
        "clip",
    ),
    (
        r"wall\s+bracket|mounting\s+bracket|fixed\s+to\s+a\s+wall\s+bracket",
        "bracket",
    ),
    (
        r"invented\s+charging\s+dock|placed\s+in\s+an?\s+invented\s+charging\s+dock|"
        r"charging\s+dock",
        "dock",
    ),
    (
        r"mounted\s+using\s+an?\s+(?:unsupported\s+)?stand|unsupported\s+stand|"
        r"product[-\s]specific\s+stand|invented\s+(?:desk\s+)?stand",
        "stand",
    ),
    (
        r"mounting\s+strap|secured\s+with\s+a\s+(?:mounting\s+)?strap",
        "strap",
    ),
    (
        r"power\s+cable\s+routed|cable\s+routed\s+(?:beside|inside|immediately)|"
        r"cables?\s+(?:inside|beside)\s+(?:or\s+immediately\s+beside\s+)?(?:the\s+)?crib",
        "product_cable",
    ),
    (
        r"\bin\s+(?:its\s+)?retail\s+(?:box|packaging)\b|invented\s+packaging|"
        r"unsupported\s+packaging",
        "packaging",
    ),
    (
        r"carrying\s+case|protective\s+(?:carrying\s+)?case|invented\s+(?:product\s+)?case",
        "case",
    ),
    (
        r"invented\s+(?:physical\s+)?connector|unsupported\s+physical\s+connector|"
        r"product[-\s]specific\s+physical\s+connector",
        "connector",
    ),
    (
        r"accessory\s+holder|attached\s+using\s+an?\s+accessory|"
        r"invented\s+(?:mounting\s+)?accessory",
        "accessory",
    ),
    (
        r"stroller[-\s]?mount(?:ed|ing)?|mounted\s+on\s+(?:a\s+|the\s+)?stroller|"
        r"clipped\s+to\s+(?:a\s+|the\s+)?stroller|attached\s+to\s+(?:a\s+|the\s+)?stroller",
        "stroller_mount",
    ),
)

STABLE_SURFACE_INSTRUCTION = (
    "Place the product fully on its original base on a dresser, shelf, table, or counter. "
    "Do not invent mounting hardware, clips, brackets, docks, straps, or product cables. "
    "Do not route cables inside or immediately beside a crib."
)

GRAPHIC_HINTS = re.compile(
    r"\b(illustration|illustrated|graphic\s+campaign|poster\s+art|flat\s+vector|"
    r"comic|collage|deliberately\s+graphic|product-design\s+service)\b",
    re.IGNORECASE,
)

USABLE_INTEL_CONFIDENCE = frozenset({"medium", "high"})


def detect_capture_style(product_info: dict, texts: Iterable[str]) -> str:
    blob = " ".join(t for t in texts if t)
    if GRAPHIC_HINTS.search(blob or ""):
        return "graphic_or_illustrated"
    requested = str(product_info.get("capture_style") or "").strip().lower()
    if requested in ("graphic_or_illustrated", "graphic", "illustrated"):
        return "graphic_or_illustrated"
    plan = (product_info or {}).get("generation_plan") or {}
    if str(plan.get("capture_style") or "").strip().lower() in (
        "graphic_or_illustrated",
        "graphic",
        "illustrated",
    ):
        return "graphic_or_illustrated"
    return "realistic_photography"


def sanitize_realistic_photo_style(text: str) -> tuple[str, bool]:
    if not text:
        return text, False
    cleaned, n = RENDER_RE.subn("lifestyle photograph", text)
    cleaned2, n2 = FLOATING_SYMBOL_RE.subn("incidental background object", cleaned)
    return cleaned2, (n + n2) > 0


def _corpus(product_info: dict, extra: str = "") -> str:
    info = product_info or {}
    dims = info.get("dimensions") or info.get("selected_dimensions") or {}
    dim_text = " ".join(str(v) for v in dims.values()) if isinstance(dims, dict) else ""
    return " ".join(
        [
            extra,
            str(info.get("description") or ""),
            str(info.get("selling_points") or ""),
            str(info.get("style_hint") or ""),
            dim_text,
            str(info.get("image_prompt") or ""),
        ]
    )


def _structured_blob(product_info: dict) -> dict:
    blob = (product_info or {}).get("structured_settings")
    return blob if isinstance(blob, dict) else {}


def _offering_kind(product_info: dict) -> str:
    blob = _structured_blob(product_info)
    return str(
        blob.get("offering_kind")
        or blob.get("offering_type")
        or product_info.get("offering_kind")
        or product_info.get("offering_type")
        or ""
    ).strip().lower()


def packaging_is_the_offering(product_info: dict) -> bool:
    blob = _structured_blob(product_info)
    if blob.get("packaging_is_offering") is True:
        return True
    kind = _offering_kind(product_info)
    return "packaging" in kind


def physical_placement_sanitization_applies(product_info: dict, texts: Iterable[str] | None = None) -> bool:
    """Only rewrite placement for physical-product photographic scenarios."""
    info = product_info or {}
    capture = detect_capture_style(info, list(texts or []) + [_corpus(info)])
    if capture == "graphic_or_illustrated":
        return False
    kind = _offering_kind(info)
    if kind in NON_PHYSICAL_OFFERING_KINDS:
        return False
    blob = _structured_blob(info)
    if kind in PHYSICAL_OFFERING_KINDS or blob.get("is_physical") is True:
        return True
    plan = info.get("generation_plan") if isinstance(info.get("generation_plan"), dict) else {}
    items = list((plan.get("reference_manifest") or {}).get("items") or [])
    has_product_ref = any(
        str(item.get("image_type") or "") == "product" or item.get("role") == "primary_subject"
        for item in items
        if isinstance(item, dict)
    )
    return bool(has_product_ref and capture == "realistic_photography")


def model_facing_image_label(order: int) -> str:
    """1-based label matching provider image-part order. Stored order stays 0-based."""
    return f"Image {int(order) + 1}"


def evidence_installations(product_info: dict) -> set[str]:
    """Trusted evidence only: structured settings and usable asset intelligence."""
    found: set[str] = set()
    blob = _structured_blob(product_info)
    raw = blob.get("supported_installations") or blob.get("allowed_installations") or []
    if isinstance(raw, str):
        raw = [raw]
    for item in raw:
        token = str(item).strip().lower().replace("-", "_").replace(" ", "_")
        if token:
            found.add(token)
            found.add(token.replace("_mount", "") if token.endswith("_mount") else token)
    if blob.get("has_clip") or blob.get("clip_included"):
        found.add("clip")
    if blob.get("has_stand"):
        found.add("stand")
    if blob.get("has_dock") or blob.get("charging_dock"):
        found.add("dock")
    if blob.get("has_wall_mount"):
        found.add("wall_mount")
        found.add("wall")
    for row in product_info.get("asset_intelligence_results") or []:
        if not isinstance(row, dict):
            continue
        confidence = str(row.get("confidence") or "").strip().lower()
        physical = row.get("physical") if isinstance(row.get("physical"), dict) else {}
        if confidence not in USABLE_INTEL_CONFIDENCE and not physical:
            continue
        for key in ("installation", "mount", "supported_installations", "attachment"):
            value = physical.get(key)
            if isinstance(value, str) and value not in ("", "unknown"):
                token = value.strip().lower().replace("-", "_").replace(" ", "_")
                found.add(token)
            elif isinstance(value, list):
                for item in value:
                    token = str(item).strip().lower().replace("-", "_").replace(" ", "_")
                    if token:
                        found.add(token)
        label = str(row.get("label") or "")
        if confidence in USABLE_INTEL_CONFIDENCE:
            for pattern, code in UNSUPPORTED_INSTALL_PATTERNS:
                if re.search(pattern, label, re.IGNORECASE):
                    found.add(code)
    return found


def detect_unsupported_installations(
    text: str,
    evidenced: set[str],
    *,
    product_info: dict | None = None,
) -> list[str]:
    hits: list[str] = []
    skip_packaging = packaging_is_the_offering(product_info or {})
    for pattern, code in UNSUPPORTED_INSTALL_PATTERNS:
        if skip_packaging and code == "packaging":
            continue
        if code == "stroller_mount":
            kind = _offering_kind(product_info or {})
            if "stroller" in kind:
                continue
        if not re.search(pattern, text or "", re.IGNORECASE):
            continue
        alias = code.replace("_mount", "")
        if code in evidenced or alias in evidenced:
            continue
        hits.append(code)
    return hits


def simplify_unsupported_placement(text: str) -> str:
    stripped = text or ""
    for pattern, _code in UNSUPPORTED_INSTALL_PATTERNS:
        stripped = re.sub(pattern, "stable surface", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    return f"{STABLE_SURFACE_INSTRUCTION} Scene purpose preserved where possible. {stripped}".strip()


def identity_contract_from_evidence(product_info: dict) -> dict[str, Any]:
    intel = product_info.get("asset_intelligence_results") or []
    labels = [str(row.get("label")) for row in intel if isinstance(row, dict) and row.get("label")]
    physical = []
    for row in intel:
        if not isinstance(row, dict):
            continue
        module = row.get("physical") or {}
        if isinstance(module, dict):
            visible = {k: v for k, v in module.items() if v not in (None, "unknown", "")}
            if visible:
                physical.append(visible)
    return {
        "authority_order": [
            "primary_product_reference",
            "approved_product_or_brand_constraints",
            "supporting_references",
            "cached_asset_intelligence",
            "product_description_semantic_context_only",
            "creative_prompt_text",
        ],
        "visible_labels": labels[:8],
        "physical_visible": physical[:4],
        "do_not_invent_hidden_geometry": True,
    }


def logo_protection_contract(product_info: dict) -> dict[str, Any]:
    from bebcare.services.logo_policy import resolve_effective_logo_mode, should_composite_logo

    mode = resolve_effective_logo_mode(product_info)
    composite = bool(should_composite_logo(product_info))
    approved = (product_info.get("logo_url") or product_info.get("brand_logo_url") or "").strip()
    spelling = str(product_info.get("brand_wordmark") or product_info.get("brand_name") or "").strip()
    return {
        "exact_case_sensitive": True,
        "if_visible": (
            "preserve exact spelling, capitalization, symbol, placement, "
            "orientation, spacing, proportions from the approved mark"
        ),
        "if_hidden_or_too_small": "logo may be absent or unobtrusive; do not invent lettering",
        "if_cannot_preserve": "prefer a clean unobtrusive region for later compositing; never approximate lettering",
        "use_controlled_compositing": composite and mode == "composite",
        "approved_logo_asset_present": bool(approved),
        "wordmark_authority": spelling or None,
        "logo_mode": mode,
        "brand_logo_version": product_info.get("brand_logo_version") or product_info.get("logo_version"),
    }


def reference_authority_block(plan_dict: dict | None) -> str:
    items = list(((plan_dict or {}).get("reference_manifest") or {}).get("items") or [])
    ordered = sorted(items, key=lambda item: item.get("order", 0))
    roles = "; ".join(
        f"{model_facing_image_label(int(item.get('order', 0)))}: {item.get('role')}"
        for item in ordered
        if item.get("role")
    )
    lines = [
        "Image 1 is the primary geometry and identity authority.",
        "Supporting references provide alternate detail or view evidence only.",
        "Supporting references must not create extra visible products unless the GenerationPlan explicitly allows a supported group.",
        "If a surface or accessory is not visible or supported, do not invent it.",
        "Preserve uncertainty rather than creating detailed unsupported geometry.",
    ]
    if roles:
        lines.append(f"Stored roles: {roles}.")
    return " ".join(lines)


def _logo_section(logo: dict) -> str:
    wordmark = str(logo.get("wordmark_authority") or "").strip()
    hidden = (
        "A naturally hidden, cropped, tiny, oblique, or blurred logo may be absent. "
        "Do not invent a sharper logo. Do not force a logo onto a surface where the "
        "selected view does not support it."
    )
    if wordmark:
        visible = (
            f'The exact case-sensitive wordmark is "{wordmark}". '
            "Preserve this spelling, capitalization, shape, spacing, and placement "
            "only when the referenced view makes the mark visible."
        )
    else:
        visible = (
            "No trusted wordmark string is available. Do not invent lettering. "
            f"{logo.get('if_visible')}"
        )
    composite = (
        "When exact reproduction is unreliable, leave a clean unobtrusive region "
        "for controlled compositing."
        if logo.get("use_controlled_compositing")
        else logo.get("if_cannot_preserve")
    )
    return (
        f"{visible} {hidden} {composite} "
        "Do not reinterpret capitalization or typography."
    )


def fidelity_prompt_prefix(plan_dict: dict) -> str:
    placement = plan_dict.get("placement") or {}
    identity = plan_dict.get("identity_contract") or {}
    logo = plan_dict.get("logo_policy") or {}
    style = plan_dict.get("capture_style") or "realistic_photography"
    photo = plan_dict.get("photographic_treatment") or ""
    simplifications = plan_dict.get("fidelity_simplifications") or []
    parts = [
        "1. Output type and purpose: commercial social still; product-accurate marketing image.",
        f"2. Reference authority: {reference_authority_block(plan_dict)}",
        f"3. Subject/configuration: {placement.get('instruction') or STABLE_SURFACE_INSTRUCTION}",
        "4. Product identity: preserve verified visible attributes from Image 1 only "
        f"(silhouette, major component relationship, controls, base, antenna if visible, "
        f"trim, indicators, color divisions, logo region). Evidence: {identity.get('visible_labels') or 'Image 1'}. "
        "Do not reconstruct hidden geometry from marketing copy.",
        f"5. Valid placement: {placement.get('instruction') or STABLE_SURFACE_INSTRUCTION}",
        f"6. Logo/screen: {_logo_section(logo)}",
        "7. Camera and lighting: compact, scene-consistent; keep cinematic language short.",
        f"8. Material/photographic treatment: {photo or PHOTOGRAPHIC_CONTRACT}."
        if style == "realistic_photography"
        else "8. Graphic or illustrated campaign style is allowed for this plan.",
        "9. Scene contents after product identity.",
        "10. Hard prohibitions: invented mounts/accessories/packaging; extra primary units; approximated logos; unsupported installation.",
    ]
    if simplifications:
        parts.append("Placement simplified: " + "; ".join(simplifications))
    coverage = str(plan_dict.get("reference_coverage") or "")
    if coverage in ("limited", "insufficient") and not plan_dict.get("coverage_constraints"):
        from bebcare.services.quality_diversity_policy import coverage_prompt

        extra = coverage_prompt(coverage)  # type: ignore[arg-type]
        if extra:
            parts.append(extra)
    if style == "realistic_photography" and plan_dict.get("selector_trace"):
        from bebcare.services.quality_diversity_policy import VARIETY_PROMPT

        parts.append(VARIETY_PROMPT)
    return " ".join(parts)


def apply_product_fidelity_prevention(product_info: dict) -> dict:
    info = product_info if product_info is not None else {}
    source = (
        (info.get("generation_provenance") or {}).get("source")
        or info.get("source")
        or SOURCE_STUDIO
    )
    if not prevention_enabled(source=source):
        return info
    from bebcare.schemas.generation_plan import dump_generation_plan
    from bebcare.services.generation_plan import plan_from_product_info

    plan = plan_from_product_info(info)
    dims = info.get("selected_dimensions") or info.get("dimensions") or {}
    dim_blob = " ".join(str(v) for v in dims.values()) if isinstance(dims, dict) else ""
    capture = detect_capture_style(info, [_corpus(info, dim_blob)])
    evidenced = evidence_installations(info)
    apply_place = physical_placement_sanitization_applies(info, [_corpus(info, dim_blob)])
    unsupported: list[str] = []
    if apply_place:
        unsupported = detect_unsupported_installations(
            _corpus(info, dim_blob), evidenced, product_info=info
        )
    simplifications: list[str] = []
    placement_instruction = "Use a scene-consistent stable support already evidenced."
    if unsupported:
        simplifications.append("unsupported_installation_simplified:" + ",".join(unsupported))
        placement_instruction = STABLE_SURFACE_INSTRUCTION
        if isinstance(dims, dict):
            updated = dict(dims)
            for key, value in list(updated.items()):
                if isinstance(value, str) and detect_unsupported_installations(
                    value, evidenced, product_info=info
                ):
                    updated[key] = simplify_unsupported_placement(value)
            info["dimensions"] = updated
            info["selected_dimensions"] = updated
    overlay = {
        "capture_style": capture,
        "photographic_treatment": PHOTOGRAPHIC_CONTRACT if capture == "realistic_photography" else None,
        "placement": {
            "surface": "stable_furniture" if unsupported else "plan_default",
            "unsupported_codes": unsupported,
            "evidenced_installations": sorted(evidenced),
            "instruction": placement_instruction,
            "simplified_from": unsupported or None,
        },
        "identity_contract": identity_contract_from_evidence(info),
        "logo_policy": logo_protection_contract(info),
        "fidelity_simplifications": simplifications,
        "fidelity_policy_version": PREVENTION_POLICY_VERSION,
    }
    provenance = info.get("generation_provenance") or {}
    trace = provenance.get("selector_trace") if isinstance(provenance.get("selector_trace"), dict) else {}
    coverage = str(trace.get("coverage") or "")
    if coverage:
        from bebcare.services.quality_diversity_policy import COVERAGE_CONSTRAINTS

        overlay["reference_coverage"] = coverage
        overlay["coverage_constraints"] = list(COVERAGE_CONSTRAINTS.get(coverage) or [])
        overlay["selector_trace"] = {
            "coverage": coverage,
            "selection_reason": trace.get("selection_reason"),
            "diversity_applied": bool(trace.get("diversity_applied")),
            "selected_ids": trace.get("selected_ids"),
            "selector_policy_version": trace.get("selector_policy_version"),
            "selection_seed": trace.get("selection_seed"),
        }
        overlay["diversity_fingerprint"] = trace.get("fingerprint")
        if coverage in ("limited", "insufficient"):
            overlay["transformation_policy"] = coverage
            dumped_constraints = list((dump_generation_plan(plan) if plan else {}).get("constraints") or [])
            dumped_constraints.append("coverage_" + coverage)
            overlay["extra_constraints"] = dumped_constraints
    dumped = dump_generation_plan(plan) if plan else {}
    dumped.update(overlay)
    if coverage:
        from bebcare.services.quality_diversity_policy import apply_coverage_to_plan_dict

        dumped = apply_coverage_to_plan_dict(dumped, coverage)
    info["generation_plan"] = dumped
    info["fidelity_guard"] = overlay
    provenance["generation_plan"] = dumped
    provenance["fidelity_simplifications"] = simplifications
    provenance["product_fidelity_prevention_mode"] = product_fidelity_prevention_mode()
    if coverage in ("limited", "insufficient"):
        info["reference_quality_notice"] = True
        from bebcare.services.quality_diversity_policy import user_facing_selector_reason

        info["reference_diagnostics"] = {
            "coverage": coverage,
            "reason": user_facing_selector_reason(trace),
            "diversity_applied": bool(trace.get("weighted_rotation_enabled")),
        }
    info["generation_provenance"] = provenance
    return info


def sanitize_final_image_prompt(prompt: str, product_info: dict) -> str:
    info = product_info or {}
    source = (
        (info.get("generation_provenance") or {}).get("source")
        or info.get("source")
        or SOURCE_STUDIO
    )
    if not prevention_enabled(source=source):
        return (prompt or "").strip()
    info = apply_product_fidelity_prevention(dict(info))
    plan = info.get("generation_plan") or {}
    capture = detect_capture_style(info, [prompt or "", _corpus(info)])
    if plan.get("capture_style") == "graphic_or_illustrated":
        capture = "graphic_or_illustrated"
    text = prompt or ""
    if capture == "realistic_photography":
        text, _changed = sanitize_realistic_photo_style(text)
    evidenced = evidence_installations(info)
    if physical_placement_sanitization_applies(info, [text]) and detect_unsupported_installations(
        text, evidenced, product_info=info
    ):
        text = simplify_unsupported_placement(text)
    prefix = fidelity_prompt_prefix(plan) if plan else ""
    if prefix:
        return f"{prefix}\n{text}".strip()
    return text.strip()
