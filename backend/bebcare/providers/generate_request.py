"""Single typed image-generation request consumed by provider adapters."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from bebcare.schemas.reference_manifest import (
    ManifestItem,
    ReferenceManifest,
)

ROLE_LABELS = {
    "primary_subject": "primary subject",
    "supporting_subject": "supporting subject (same offering)",
    "scene": "scene context (environment only; not a product)",
    "legacy_reference": "legacy reference",
}


class GenerateImageRequest(BaseModel):
    prompt: str
    negative_prompt: str = ""
    size: str = "2048x2048"
    model: Optional[str] = None
    references: ReferenceManifest = Field(default_factory=ReferenceManifest)
    annotate_roles: bool = False
    validated_prompt_hash: Optional[str] = None

    def ordered_urls(self) -> list[str]:
        return self.references.ordered_urls()

    def prompt_with_role_labels(self) -> str:
        body = (self.prompt or "").strip()
        if self.validated_prompt_hash:
            return body
        if not self.annotate_roles or not self.references.items:
            return body
        lines = []
        for index, item in enumerate(sorted(self.references.items, key=lambda i: i.order), start=1):
            label = ROLE_LABELS.get(item.role, item.role)
            lines.append(f"Image {index} ({label}).")
        prefix = " ".join(lines)
        return f"{prefix}\n\n{body}" if body else prefix

    @classmethod
    def from_legacy(
        cls,
        prompt: str,
        negative_prompt: str = "",
        size: str = "2048x2048",
        model: Optional[str] = None,
        reference_images: Optional[list[str]] = None,
        *,
        annotate_roles: bool = False,
    ) -> "GenerateImageRequest":
        """URL-only fallback. Roles are neutral; annotations stay off.

        Unknown scene-first lists must not be labeled as grounded product roles.
        `annotate_roles` is accepted for call-site compatibility and ignored.
        """
        items: list[ManifestItem] = []
        order = 0
        for url in reference_images or []:
            if not url:
                continue
            items.append(
                ManifestItem(
                    order=order,
                    role="legacy_reference",
                    image_id=None,
                    cdn_url=url,
                    image_type="product",
                    authority="legacy_url",
                )
            )
            order += 1
        return cls(
            prompt=prompt or "",
            negative_prompt=negative_prompt or "",
            size=size,
            model=model,
            references=ReferenceManifest(items=items),
            annotate_roles=False,
        )


def resolve_generate_image_request(
    *,
    prompt: str = "",
    negative_prompt: str = "",
    reference_images: Optional[list[str]] = None,
    size: str = "2048x2048",
    model: Optional[str] = None,
    request: Optional[GenerateImageRequest] = None,
) -> GenerateImageRequest:
    if request is not None:
        return request
    return GenerateImageRequest.from_legacy(
        prompt,
        negative_prompt,
        size,
        model,
        reference_images,
    )
