from bebcare.providers.generate_request import GenerateImageRequest
from bebcare.schemas.reference_manifest import ManifestItem, ReferenceManifest


def test_from_legacy_isolated():
    req = GenerateImageRequest.from_legacy(
        "prompt",
        "neg",
        "1024x1024",
        "model-a",
        ["https://cdn.test/a.jpg", "https://cdn.test/b.jpg"],
    )
    assert [item.authority for item in req.references.items] == ["legacy_url", "legacy_url"]
    assert [item.role for item in req.references.items] == ["legacy_reference", "legacy_reference"]
    assert [item.order for item in req.references.items] == [0, 1]
    assert req.ordered_urls() == ["https://cdn.test/a.jpg", "https://cdn.test/b.jpg"]
    assert req.annotate_roles is False
    labeled = GenerateImageRequest.from_legacy(
        "prompt",
        "neg",
        "1024x1024",
        "model-a",
        ["https://cdn.test/a.jpg", "https://cdn.test/b.jpg"],
        annotate_roles=True,
    )
    assert labeled.annotate_roles is False
    assert "Image 1" not in labeled.prompt_with_role_labels()
    assert "primary subject" not in labeled.prompt_with_role_labels()


def test_role_labels_follow_canonical_order():
    req = GenerateImageRequest(
        prompt="redraw",
        size="1024x1024",
        annotate_roles=True,
        references=ReferenceManifest(
            items=[
                ManifestItem(
                    order=0,
                    role="primary_subject",
                    cdn_url="https://cdn.test/p.jpg",
                    image_type="product",
                    authority="preferred",
                ),
                ManifestItem(
                    order=1,
                    role="supporting_subject",
                    cdn_url="https://cdn.test/q.jpg",
                    image_type="product",
                    authority="suitability",
                ),
                ManifestItem(
                    order=2,
                    role="scene",
                    cdn_url="https://cdn.test/s.jpg",
                    image_type="scene",
                    authority="suitability",
                ),
            ]
        ),
    )
    labeled = req.prompt_with_role_labels()
    assert labeled.index("Image 1") < labeled.index("Image 2") < labeled.index("Image 3")
    assert "primary subject" in labeled
    assert "scene context" in labeled
    assert req.ordered_urls() == [
        "https://cdn.test/p.jpg",
        "https://cdn.test/q.jpg",
        "https://cdn.test/s.jpg",
    ]
