"""Phase 1B compact internal generation plan (not user-facing)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from bebcare.schemas.reference_manifest import ReferenceManifest

DisplayConfig = Literal[
    "single_primary",
    "multi_reference_same_subject",
    "reference_supported_group",
    "scene_context",
]
SupportingPolicy = Literal["none", "same_offering_only", "explicit_group"]
SceneMode = Literal["none", "lifestyle", "unsupported"]
PLAN_VERSION = "generation_plan_v1"

ALLOWED_CHANGES = (
    "scene_consistent_perspective",
    "supported_orientation",
    "scale_to_scene",
    "scene_lighting",
    "reflection",
    "shadow",
    "focus",
    "environmental_color",
    "credible_occlusion",
)
FORBIDDEN_CHANGES = (
    "duplicate_primary_subjects",
    "invented_packaging",
    "invented_mounts",
    "invented_accessories",
    "unsupported_faces_or_views",
    "generated_small_text",
    "handheld_physical_replacement",
    "identity_structure_change",
    "identity_proportion_change",
    "visible_relationship_change",
)
PHYSICAL_OFFERING_KINDS = frozenset(
    {"physical", "physical_product", "hardware", "goods", "sku_physical"}
)
NON_PHYSICAL_OFFERING_KINDS = frozenset(
    {"software", "saas", "service", "services", "event", "events", "mixed", "unknown"}
)


class SubjectSpec(BaseModel):
    primary_subject_count: int = 1
    duplicate_primary_subjects_allowed: bool = False
    supporting_subject_policy: SupportingPolicy = "none"
    physical_instance_limit: Optional[int] = None


class TextPolicy(BaseModel):
    generated_small_text: Literal["prohibited"] = "prohibited"
    watermarks_qr_urls: Literal["prohibited"] = "prohibited"


class BrandPolicy(BaseModel):
    extra_brand_names: Literal["prohibited"] = "prohibited"
    preserve_visible_branding: bool = True


class GenerationPlan(BaseModel):
    version: Literal["generation_plan_v1"] = PLAN_VERSION
    display_config: DisplayConfig
    display_configuration: DisplayConfig | None = None
    subject: SubjectSpec = Field(default_factory=SubjectSpec)
    subject_spec: SubjectSpec | None = None
    handheld_physical_replacement: Literal["prohibited"] = "prohibited"
    scene_mode: SceneMode = "none"
    allowed_changes: list[str] = Field(default_factory=lambda: list(ALLOWED_CHANGES))
    forbidden_changes: list[str] = Field(default_factory=lambda: list(FORBIDDEN_CHANGES))
    text_policy: TextPolicy = Field(default_factory=TextPolicy)
    brand_policy: BrandPolicy = Field(default_factory=BrandPolicy)
    constraints: list[str] = Field(default_factory=list)
    reference_manifest: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _sync_aliases(self) -> "GenerationPlan":
        self.display_configuration = self.display_config
        self.subject_spec = self.subject
        return self


def dump_generation_plan(plan: GenerationPlan) -> dict[str, Any]:
    return plan.model_dump()


def load_generation_plan(raw: Any) -> GenerationPlan | None:
    if not raw or not isinstance(raw, dict):
        return None
    try:
        return GenerationPlan.model_validate(raw)
    except Exception:
        return None


def group_evidence(*, manifest: ReferenceManifest, structured_group: Any = None) -> bool:
    if structured_group:
        return True
    authorities = {item.authority for item in manifest.items}
    return "structured_settings" in authorities


def resolve_physical_instance_limit(
    *,
    product_info: dict | None = None,
    structured_group: Any = None,
) -> Optional[int]:
    """Nullable unless explicit physical-offering or instance-limit evidence exists."""
    info = product_info or {}
    settings = info.get("structured_settings")
    blob: dict[str, Any] = dict(settings) if isinstance(settings, dict) else {}
    if isinstance(structured_group, dict):
        for key in (
            "offering_kind",
            "offering_type",
            "is_physical",
            "physical_instance_limit",
        ):
            if key in structured_group and key not in blob:
                blob[key] = structured_group[key]
    kind = str(
        blob.get("offering_kind")
        or blob.get("offering_type")
        or info.get("offering_kind")
        or ""
    ).strip().lower()
    if kind in NON_PHYSICAL_OFFERING_KINDS:
        return None
    raw_limit = blob.get("physical_instance_limit", info.get("physical_instance_limit"))
    if raw_limit is None:
        return None
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return None
    if limit < 0:
        return None
    if kind in PHYSICAL_OFFERING_KINDS or blob.get("is_physical") is True:
        return limit
    if "physical_instance_limit" in blob:
        return limit
    return None


def build_generation_plan(
    manifest: ReferenceManifest,
    *,
    structured_group: Any = None,
    requested_display_config: DisplayConfig | None = None,
    product_info: dict | None = None,
) -> GenerationPlan:
    items = list(manifest.items)
    supporting = [item for item in items if item.role == "supporting_subject"]
    has_scene = any(item.role == "scene" for item in items)
    evidence = group_evidence(manifest=manifest, structured_group=structured_group)
    if requested_display_config == "reference_supported_group" and not evidence:
        raise ValueError("reference_supported_group requires explicit group evidence")

    if requested_display_config and requested_display_config != "reference_supported_group":
        display = requested_display_config
    elif evidence:
        display = "reference_supported_group"
    elif has_scene:
        display = "scene_context"
    elif supporting:
        display = "multi_reference_same_subject"
    else:
        display = "single_primary"

    if display == "reference_supported_group" and not evidence:
        raise ValueError("reference_supported_group requires explicit group evidence")

    policy: SupportingPolicy = "none"
    if display == "reference_supported_group":
        policy = "explicit_group"
    elif supporting:
        policy = "same_offering_only"

    scene_mode: SceneMode = "lifestyle" if has_scene else "none"
    instance_limit = resolve_physical_instance_limit(
        product_info=product_info, structured_group=structured_group
    )
    constraints = [
        "controlled_re_render",
        "no_duplicate_primary_subjects",
        "no_invented_packaging",
        "no_invented_mounts",
        "no_unsupported_views",
        "no_generated_small_text",
        "handheld_physical_replacement_prohibited",
    ]
    intel = (product_info or {}).get("asset_intelligence") or {}
    if not intel:
        intel = ((product_info or {}).get("generation_provenance") or {}).get(
            "asset_intelligence"
        ) or {}
    enabled = bool(intel.get("enabled") and intel.get("cache_hit"))
    selected_intel = (
        (product_info or {}).get("asset_intelligence_results")
        or intel.get("results")
        or []
    )
    has_screenshot = False
    has_packaging = False
    for row in selected_intel:
        if not isinstance(row, dict):
            continue
        if row.get("is_screenshot"):
            has_screenshot = True
        if row.get("is_packaging"):
            has_packaging = True
    if enabled and has_screenshot:
        constraints.append("screenshot_not_physical_instance")
    if enabled and has_packaging:
        constraints.append("packaging_not_silent_hero")
    primary_count = 1
    if display == "reference_supported_group" and isinstance(structured_group, dict):
        raw_count = structured_group.get("primary_subject_count") or structured_group.get(
            "visible_subject_count"
        )
        if raw_count is not None:
            try:
                primary_count = max(1, int(raw_count))
            except (TypeError, ValueError):
                primary_count = 1
    return GenerationPlan(
        display_config=display,
        subject=SubjectSpec(
            primary_subject_count=primary_count,
            duplicate_primary_subjects_allowed=False,
            supporting_subject_policy=policy,
            physical_instance_limit=instance_limit,
        ),
        scene_mode=scene_mode,
        allowed_changes=list(ALLOWED_CHANGES),
        forbidden_changes=list(FORBIDDEN_CHANGES),
        constraints=constraints,
        reference_manifest=manifest.model_dump(),
    )


def _locale(locale: str) -> str:
    value = (locale or "en").lower()
    return "zh" if value.startswith("zh") else "en"


def render_generation_plan_contract(plan: GenerationPlan, locale: str = "en") -> str:
    """Model-facing contract built only from the stored GenerationPlan."""
    spec = plan.subject_spec or plan.subject
    display = plan.display_configuration or plan.display_config
    items = (plan.reference_manifest or {}).get("items") or []
    ordered = sorted(items, key=lambda item: item.get("order", 0))
    role_line = "; ".join(
        f"Image {int(item.get('order', 0)) + 1}={item.get('role')}"
        for item in ordered
        if item.get("cdn_url")
    )
    allowed = ", ".join(plan.allowed_changes)
    forbidden = ", ".join(plan.forbidden_changes)
    limit = spec.physical_instance_limit
    if _locale(locale) == "zh":
        support = {
            "single_primary": "辅助参考只提供同一主商品的细节或视角，不得生成第二个主产品。",
            "multi_reference_same_subject": "辅助参考只提供同一主商品的细节或视角，不得生成重复主产品。",
            "reference_supported_group": "仅在已有明确结构化证据时才允许多个可见主体；不得根据参考图数量推断组合。",
            "scene_context": "场景图只是环境证据；场景中已有的无关物体不得当成额外目标主体。",
        }.get(display, "")
        group = (
            "允许多个可见主体，因为存在明确结构化组合证据。"
            if display == "reference_supported_group"
            else "禁止把参考数量当成多主体依据。"
        )
        scene = (
            "场景模式为环境/生活方式；无关物体不是目标主体。"
            if plan.scene_mode == "lifestyle"
            else f"场景模式：{plan.scene_mode}。"
        )
        phys = (
            f"物理实例上限：{limit}。"
            if limit is not None
            else "未设定物理实例上限（未知或非实物供给不得套用实物件数规则）。"
        )
        text = plan.text_policy
        brand = plan.brand_policy
        return (
            f"受控重绘，按已存储 GenerationPlan 执行。展示配置：{display}。"
            f"主主体数量：{spec.primary_subject_count}。"
            f"禁止重复主主体：{not spec.duplicate_primary_subjects_allowed}。"
            f"辅助策略：{spec.supporting_subject_policy}。{support}{group}{scene}{phys}"
            f"允许：{allowed}。禁止：{forbidden}。"
            f"文字：禁止生成小字/水印/二维码/网址（{text.generated_small_text}）。"
            f"品牌：禁止额外品牌名（{brand.extra_brand_names}）；保留参考图可见品牌关系。"
            f"参考顺序：{role_line or '无'}。"
            "禁止手持实物替换。保留身份结构、比例、品牌与可见关系。"
        )
    support = {
        "single_primary": (
            "Supporting references are alternate detail or viewpoint evidence for the same "
            "primary offering and must not produce duplicate primary subjects."
        ),
        "multi_reference_same_subject": (
            "Supporting references are alternate detail or viewpoint evidence for the same "
            "primary offering and must not produce duplicate primary subjects."
        ),
        "reference_supported_group": (
            "Multiple visible subjects are allowed only because explicit structured evidence exists. "
            "Do not infer a group from the number of supplied references."
        ),
        "scene_context": (
            "The scene is environmental evidence. An existing unrelated object must not be "
            "interpreted as an additional target subject."
        ),
    }.get(display, "")
    phys = (
        f"Physical instance limit: {limit}."
        if limit is not None
        else "No physical-instance limit (do not assume a physical count for unknown or non-physical offerings)."
    )
    text = plan.text_policy
    brand = plan.brand_policy
    return (
        f"Controlled re-render from the stored GenerationPlan. "
        f"display_configuration={display}. "
        f"subject_spec.primary_subject_count={spec.primary_subject_count}. "
        f"duplicate_primary_subjects_allowed={spec.duplicate_primary_subjects_allowed}. "
        f"supporting_subject_policy={spec.supporting_subject_policy}. "
        f"{support} scene_mode={plan.scene_mode}. {phys} "
        f"allowed_changes={allowed}. forbidden_changes={forbidden}. "
        f"text_policy: generated small text {text.generated_small_text}; "
        f"watermarks/QR/URLs {text.watermarks_qr_urls}. "
        f"brand_policy: extra brand names {brand.extra_brand_names}; "
        f"preserve visible branding={brand.preserve_visible_branding}. "
        f"reference roles/order: {role_line or 'none'}. "
        "Handheld physical-product replacement is prohibited. "
        "Preserve identity-defining structure, proportions, branding, and visible relationships. "
        "Allow scene-consistent perspective, supported orientation, scale, lighting, reflection, "
        "shadow, focus, environmental color, and credible occlusion."
    )


def render_fidelity_contract_suffix(product_info: dict | None, locale: str = "en") -> str:
    info = product_info or {}
    overlay = info.get("fidelity_guard") or {}
    plan_dict = info.get("generation_plan") if isinstance(info.get("generation_plan"), dict) else {}
    if not overlay and not (plan_dict or {}).get("fidelity_policy_version"):
        return ""
    from bebcare.services.product_fidelity_prevention import fidelity_prompt_prefix

    payload = dict(plan_dict)
    payload.update(overlay)
    prefix = fidelity_prompt_prefix(payload)
    if not prefix:
        return ""
    if _locale(locale) == "zh":
        return "产品保真：" + prefix
    return "Product fidelity: " + prefix
