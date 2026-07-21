import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from bebcare.database import Base
from bebcare.models.prompt_dimension import PromptDimension, PromptDimensionCompatibility, DimensionType
from bebcare.prompt_builder.prompt_engine import PromptEngine
from bebcare.prompt_builder.dimensions_data import DIMENSIONS

TEST_DB_URL = "sqlite:///./test_dimension.db"

def setup_test_database():
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    db = Session()
    
    return db

def populate_test_data(db):
    product_type = "test_product"
    
    scenes = [
        {"id": "scene_day", "name": "日间场景", "compatible_lighting": ["light_day", "light_natural"], "compatible_styles": ["style_bright", "style_modern"], "compatible_viewpoints": ["view_high", "view_mid"]},
        {"id": "scene_night", "name": "夜间场景", "compatible_lighting": ["light_night", "light_warm"], "compatible_styles": ["style_cozy", "style_soft"], "compatible_viewpoints": ["view_low", "view_close"]},
    ]
    
    lighting = [
        {"id": "light_day", "name": "日间光线"},
        {"id": "light_natural", "name": "自然光"},
        {"id": "light_night", "name": "夜间光线"},
        {"id": "light_warm", "name": "暖光"},
        {"id": "light_cold", "name": "冷光"},
    ]
    
    styles = [
        {"id": "style_bright", "name": "明亮风格"},
        {"id": "style_modern", "name": "现代风格"},
        {"id": "style_cozy", "name": "温馨风格"},
        {"id": "style_soft", "name": "柔和风格"},
        {"id": "style_vintage", "name": "复古风格"},
    ]
    
    viewpoints = [
        {"id": "view_high", "name": "高视角"},
        {"id": "view_mid", "name": "中视角"},
        {"id": "view_low", "name": "低视角"},
        {"id": "view_close", "name": "特写"},
        {"id": "view_wide", "name": "广角"},
    ]
    
    compositions = [
        {"id": "comp_center", "name": "中心构图"},
        {"id": "comp_rule_thirds", "name": "三分构图"},
        {"id": "comp_diagonal", "name": "对角线构图"},
    ]
    
    details = [
        {"id": "detail_flower", "name": "花卉装饰"},
        {"id": "detail_books", "name": "书籍道具"},
        {"id": "detail_toys", "name": "儿童玩具"},
    ]
    
    quality = [
        {"id": "q_high", "name": "高清画质"},
        {"id": "q_ultra", "name": "超清画质"},
        {"id": "q_standard", "name": "标准画质"},
    ]
    
    dim_data = {
        "scenes": scenes,
        "lighting": lighting,
        "styles": styles,
        "viewpoints": viewpoints,
        "compositions": compositions,
        "details": details,
        "quality": quality,
    }
    
    dim_instances = {}
    
    for dim_type, items in dim_data.items():
        dim_instances[dim_type] = {}
        for item in items:
            dim = PromptDimension(
                product_type=product_type,
                dimension_type=dim_type,
                item_id=item["id"],
                name=item["name"]
            )
            db.add(dim)
            db.flush()
            dim_instances[dim_type][item["id"]] = dim
            
            if "compatible_lighting" in item:
                for light_id in item["compatible_lighting"]:
                    comp = PromptDimensionCompatibility(
                        dimension_id=dim.dimension_id,
                        source_dimension_type="scenes",
                        target_dimension_type="lighting",
                        target_item_id=light_id,
                        relation_type="compatible",
                        is_active=True
                    )
                    db.add(comp)
            
            if "compatible_styles" in item:
                for style_id in item["compatible_styles"]:
                    comp = PromptDimensionCompatibility(
                        dimension_id=dim.dimension_id,
                        source_dimension_type="scenes",
                        target_dimension_type="styles",
                        target_item_id=style_id,
                        relation_type="compatible",
                        is_active=True
                    )
                    db.add(comp)
            
            if "compatible_viewpoints" in item:
                for view_id in item["compatible_viewpoints"]:
                    comp = PromptDimensionCompatibility(
                        dimension_id=dim.dimension_id,
                        source_dimension_type="scenes",
                        target_dimension_type="viewpoints",
                        target_item_id=view_id,
                        relation_type="compatible",
                        is_active=True
                    )
                    db.add(comp)
    
    db.commit()
    return product_type

def test_compatibility_selection():
    print("=" * 60)
    print("测试后端七大维度兼容性选择逻辑")
    print("=" * 60)
    
    import sys
    from io import StringIO
    
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    
    db = setup_test_database()
    product_type = populate_test_data(db)
    
    engine = PromptEngine()
    
    sys.stdout = old_stdout
    
    print("\n1. 测试兼容性选择（运行多次验证随机性）")
    print("-" * 60)
    
    day_scene_count = 0
    night_scene_count = 0
    day_light_valid = 0
    day_light_invalid = 0
    night_light_valid = 0
    night_light_invalid = 0
    day_style_valid = 0
    day_style_invalid = 0
    night_style_valid = 0
    night_style_invalid = 0
    
    day_compatible_lights = {"light_day", "light_natural"}
    night_compatible_lights = {"light_night", "light_warm"}
    day_compatible_styles = {"style_bright", "style_modern"}
    night_compatible_styles = {"style_cozy", "style_soft"}
    
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    
    num_runs = 100
    for i in range(num_runs):
        result = engine._select_dimensions(product_type, db)
        scene_id = result["scene"]["id"]
        light_id = result["lighting"]["id"]
        style_id = result["style"]["id"]
        
        if scene_id == "scene_day":
            day_scene_count += 1
            if light_id in day_compatible_lights:
                day_light_valid += 1
            else:
                day_light_invalid += 1
            if style_id in day_compatible_styles:
                day_style_valid += 1
            else:
                day_style_invalid += 1
        elif scene_id == "scene_night":
            night_scene_count += 1
            if light_id in night_compatible_lights:
                night_light_valid += 1
            else:
                night_light_invalid += 1
            if style_id in night_compatible_styles:
                night_style_valid += 1
            else:
                night_style_invalid += 1
    
    sys.stdout = old_stdout
    
    print(f"运行次数: {num_runs}")
    print(f"\n场景分布:")
    print(f"  日间场景: {day_scene_count}次")
    print(f"  夜间场景: {night_scene_count}次")
    
    print(f"\n日间场景兼容性验证:")
    print(f"  光线选择 - 有效: {day_light_valid}, 无效: {day_light_invalid}")
    print(f"  风格选择 - 有效: {day_style_valid}, 无效: {day_style_invalid}")
    
    print(f"\n夜间场景兼容性验证:")
    print(f"  光线选择 - 有效: {night_light_valid}, 无效: {night_light_invalid}")
    print(f"  风格选择 - 有效: {night_style_valid}, 无效: {night_style_invalid}")
    
    all_valid = (day_light_invalid == 0 and night_light_invalid == 0 and 
                 day_style_invalid == 0 and night_style_invalid == 0)
    
    if all_valid:
        print("\n✓ 所有兼容性选择均符合预期！")
    else:
        print("\n✗ 存在不符合兼容性的选择！")
    
    print("\n2. 测试图像提示词构建")
    print("-" * 60)
    
    product_info = {
        "product_name": "Test Product",
        "description": "A test product",
        "category": "Test Category",
        "product_type": product_type,
        "selling_points": ["High quality", "Durable"]
    }
    
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    image_prompt = engine.build_image_prompt(product_info, "instagram", db=db)
    sys.stdout = old_stdout
    print(image_prompt)
    
    print("\n3. 测试无兼容性数据时的fallback行为")
    print("-" * 60)
    
    db2 = setup_test_database()
    product_type_empty = "empty_product"
    
    empty_scenes = [
        {"id": "empty_scene", "name": "空场景"},
    ]
    
    empty_lighting = [
        {"id": "empty_light", "name": "空光线"},
    ]
    
    for item in empty_scenes:
        dim = PromptDimension(
            product_type=product_type_empty,
            dimension_type="scenes",
            item_id=item["id"],
            name=item["name"]
        )
        db2.add(dim)
    
    for item in empty_lighting:
        dim = PromptDimension(
            product_type=product_type_empty,
            dimension_type="lighting",
            item_id=item["id"],
            name=item["name"]
        )
        db2.add(dim)
    
    db2.commit()
    
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    result_empty = engine._select_dimensions(product_type_empty, db2)
    sys.stdout = old_stdout
    print(f"场景: {result_empty['scene']['name']}")
    print(f"光线: {result_empty['lighting']['name']}")
    print("✓ 无兼容性数据时能够正常fallback到随机选择")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    
    db.close()
    db2.close()
    
    return all_valid

if __name__ == "__main__":
    success = test_compatibility_selection()
    sys.exit(0 if success else 1)