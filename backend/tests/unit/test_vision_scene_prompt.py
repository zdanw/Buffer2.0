from bebcare.prompt_builder.prompt_locale import (
    strip_vision_prompt_preamble,
    vision_scene_fusion_user_prompt_text,
    vision_scene_image_prompt_system_prompt,
)


def test_strip_human_preamble_from_vision_output():
    raw = (
        "基于图一场景参考与图二产品参考，以下是严格遵循指南的最终中文图像提示词：\n\n"
        "将图二中的空气净化器融合进图一场景，以提供的参考图为唯一标准。"
    )
    out = strip_vision_prompt_preamble(raw)
    assert out.startswith("将图二中的空气净化器融合")
    assert "以下是" not in out


def test_scene_fusion_user_prompt_orders_fusion_and_product_fields():
    text = vision_scene_fusion_user_prompt_text(
        "Bebcare Air Purifiers", "Air Purifiers", "zh"
    )
    assert "Bebcare Air Purifiers" in text
    assert "Air Purifiers" in text
    assert "第一句必须是融合指令" in text
    assert "将图二中的「Bebcare Air Purifiers」融合进图一场景" in text
    assert "手持产品的宣传/种草画面" in text
    assert "目标用户" in text
    assert "禁止改为桌面摆放或悬浮" in text
    assert "禁止开场白" in text


def test_scene_fusion_user_prompt_hand_held_promo_en():
    text = vision_scene_fusion_user_prompt_text(
        "Baby Monitor", "Video Monitor", "en"
    )
    assert "hand-held product promo" in text
    assert "target audience" in text
    assert "replace the product in their hand" in text
    assert "do not place on a table" in text


def test_default_scene_fusion_system_prompt_hand_held_global():
    zh = vision_scene_image_prompt_system_prompt("zh")
    en = vision_scene_image_prompt_system_prompt("en")
    assert "手持展示替换" in zh
    assert "目标用户" in zh
    assert "hand-held replacement" in en
    assert "target audience" in en
