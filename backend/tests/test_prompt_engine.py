import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"Loaded environment from {env_path}")

os.chdir(os.path.join(os.path.dirname(__file__), '..'))

from bebcare.prompt_builder.prompt_engine import prompt_engine
from bebcare.generator.content_generator import ContentGenerator
from bebcare.database import get_db, engine, Base
from bebcare.models import Product, ProductImage

Base.metadata.create_all(bind=engine)
print(f"Database tables initialized, database path: {engine.url}")

# 创建ContentGenerator实例用于测试两级prompt处理
content_generator = ContentGenerator()

def get_real_products():
    try:
        db = next(get_db())
        products = db.query(Product).all()
        result = []
        
        for product in products:
            images = db.query(ProductImage).filter(ProductImage.product_id == product.product_id).all()
            product_images = [img for img in images if img.image_type == "product"]
            scene_images = [img for img in images if img.image_type == "scene"]
            
            result.append({
                "product_id": product.product_id,
                "product_name": product.product_name,
                "category": product.category,
                "description": product.description,
                "tags": product.tags,
                "brand_voice": product.brand_voice,
                "product_images_count": len(product_images),
                "scene_images_count": len(scene_images),
                "product_images": [img.cdn_url for img in product_images],
                "scene_images": [img.cdn_url for img in scene_images],
                "reference_images": [img.cdn_url for img in images]
            })
        return result
    except Exception as e:
        print(f"Database query failed: {e}")
        return []

def print_prompt_result(title, prompt, max_lines=15, show_line_numbers=False):
    print(f"\n{'='*70}")
    print(f"【{title}】")
    print(f"{'='*70}")
    
    lines = prompt.split('\n')
    for i, line in enumerate(lines[:max_lines], 1):
        if show_line_numbers:
            print(f"{i:3d} | {line}")
        else:
            print(f"{line}")
    
    if len(lines) > max_lines:
        print(f"... (共 {len(lines)} 行，总计 {len(prompt)} 字符)")

def show_full_prompt_to_model(prompt_type, product_info, platform="instagram", style_hint=None):
    """展示最终发送给模型的完整提示词（系统提示词 + 用户提示词）"""
    system_prompt = prompt_engine.system_prompt.strip()
    
    if prompt_type == "copywriting":
        user_prompt = prompt_engine.build_copywriting_prompt(product_info, platform)
    elif prompt_type == "image":
        user_prompt = prompt_engine.build_image_prompt(product_info, platform, style_hint)
    elif prompt_type == "scene_reference":
        user_prompt = prompt_engine.build_scene_reference_prompt(product_info, platform, style_hint)
    else:
        user_prompt = ""
    
    full_prompt = f"System Prompt:\n{system_prompt}\n\n---\n\nUser Prompt:\n{user_prompt}"
    return full_prompt, system_prompt, user_prompt

def show_two_stage_image_prompts(product_info, platform="instagram", style_hint=None):
    """展示两级图像prompt处理流程（实际调用DeepSeek API）"""
    # 第一级：元prompt（发送给DeepSeek）
    meta_prompt = prompt_engine.build_image_prompt(product_info, platform, style_hint)
    meta_system_prompt = content_generator.image_prompt_system_prompt.strip()
    
    # 第二级：实际调用DeepSeek API获取最终prompt
    print("\n" + "="*50)
    print("正在调用 DeepSeek API 生成图像描述...")
    print("="*50)
    
    try:
        final_prompt = content_generator._call_deepseek(meta_prompt, meta_system_prompt, 200)
        print("\n" + "="*50)
        print("DeepSeek API 调用成功!")
        print("="*50)
    except Exception as e:
        print(f"\nDeepSeek API 调用失败: {e}")
        print("将显示元prompt供手动参考...")
        final_prompt = f"[API调用失败 - 请参考元prompt手动生成]\n{meta_prompt[:500]}..."
    
    negative_prompt = prompt_engine.build_negative_prompt()
    
    return {
        "meta_system_prompt": meta_system_prompt,
        "meta_prompt": meta_prompt,
        "final_prompt": final_prompt,
        "negative_prompt": negative_prompt
    }

def test_single_prompt(product_info, platform="instagram", style="storytelling"):
    print(f"\n{'='*70}")
    print(f"Product: {product_info['product_name']}")
    print(f"Category: {product_info['category']}")
    print(f"Platform: {platform.upper()} | Style: {style}")
    print(f"{'='*70}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 第一部分：文案生成 Prompt（发送给 DeepSeek）
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n" + "🔹"*35)
    print("【📝 第一级：文案生成 Prompt → 发送给 DeepSeek 大模型】")
    print("🔹"*35)
    full_copy_prompt, sys_copy, user_copy = show_full_prompt_to_model("copywriting", product_info, platform)
    print_prompt_result("System Prompt (DeepSeek)", sys_copy, max_lines=8)
    print_prompt_result("User Prompt (文案生成请求)", user_copy, max_lines=15)

    # ═══════════════════════════════════════════════════════════════════════════
    # 第二部分：图像生成 - 两级 Prompt 处理流程
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n" + "🔹"*35)
    print("【🖼️ 图像生成 - 两级 Prompt 处理流程】")
    print("🔹"*35)
    
    two_stage = show_two_stage_image_prompts(product_info, platform, style)
    
    # 第一级：元 Prompt → DeepSeek
    print("\n" + "─"*35)
    print("【第一级：元 Prompt → 发送给 DeepSeek 生成具体图像描述】")
    print("─"*35)
    print_prompt_result("System Prompt (DeepSeek - 图像Prompt工程师)", two_stage["meta_system_prompt"], max_lines=10)
    print_prompt_result("User Prompt (元Prompt - 包含所有维度选项)", two_stage["meta_prompt"], max_lines=25)
    
    # 第二级：最终 Prompt → 豆包
    print("\n" + "─"*35)
    print("【第二级：最终 Prompt → 发送给 豆包 图像生成模型】")
    print("─"*35)
    print_prompt_result("Final Prompt (DeepSeek输出的具体图像描述)", two_stage["final_prompt"], max_lines=10)
    print_prompt_result("Negative Prompt (负面提示词)", two_stage["negative_prompt"], max_lines=3)
    
    print("\n" + "💡"*35)
    print("【流程说明】")
    print("💡"*35)
    print("""
流程图：
┌─────────────────────────────────────────────────────────────────┐
│  1. build_image_prompt() 生成元prompt（包含所有维度选项）        │
│         ↓                                                      │
│  2. 发送给 DeepSeek 大模型，生成具体的图像描述                  │
│         ↓                                                      │
│  3. 将具体描述作为最终prompt发送给豆包图像生成API                │
└─────────────────────────────────────────────────────────────────┘

优点：
- DeepSeek大模型擅长理解复杂指令和做选择
- 豆包图像生成模型专注于根据具体描述生成高质量图像
""")

    # ═══════════════════════════════════════════════════════════════════════════
    # 第三部分：场景参考模式（如果有场景图）
    # ═══════════════════════════════════════════════════════════════════════════
    if product_info['scene_images_count'] > 0:
        print("\n" + "🔹"*35)
        print("【🎬 场景参考模式 Prompt → 直接发送给 豆包】")
        print("🔹"*35)
        print("（场景参考模式不经过DeepSeek处理，直接发送给豆包）")
        full_scene_prompt, sys_scene, user_scene = show_full_prompt_to_model("scene_reference", product_info, platform, style)
        print_prompt_result("User Prompt (场景参考指令)", user_scene, max_lines=10)

def interactive_test():
    products = get_real_products()

    print("="*70)
    print(" Bebcare Prompt Engine - Full Prompt Display Tool ")
    print("="*70)
    print("本工具展示最终发送给AI模型的完整提示词内容")
    print("="*70)
    print()

    platforms = ["instagram", "facebook", "twitter"]
    styles = ["storytelling", "lifestyle", "minimalist"]

    if products:
        print("【Products in Database】")
        for i, product in enumerate(products, 1):
            print(f"{i}. {product['product_name']}")
            print(f"   Category: {product['category']}")
            print(f"   Images: {product['product_images_count']} product + {product['scene_images_count']} scene")
            print()

        while True:
            try:
                choice = input("Select product number (or 'c' for custom product, 'q' to quit): ")
                
                if choice.lower() == 'q':
                    print("\nExiting test")
                    break
                elif choice.lower() == 'c':
                    print("\nCreate custom test product")
                    custom_product = {
                        "product_name": input("Product name: ").strip() or "Test Product",
                        "category": input("Category: ").strip() or "Test Category",
                        "description": input("Description: ").strip() or "This is a test product",
                        "tags": input("Tags (comma separated): ").strip() or "test,demo",
                        "brand_voice": input("Brand voice: ").strip() or "Professional",
                        "product_images_count": 1,
                        "scene_images_count": 1,
                        "product_images": [],
                        "scene_images": [],
                        "reference_images": []
                    }
                    
                    print("\nSelect platform and style:")
                    for i, p in enumerate(platforms, 1):
                        print(f"{i}. {p}")
                    p_choice = int(input(f"Platform (1-{len(platforms)}): ")) - 1
                    platform = platforms[p_choice] if 0 <= p_choice < len(platforms) else "instagram"
                    
                    for i, s in enumerate(styles, 1):
                        print(f"{i}. {s}")
                    s_choice = int(input(f"Style (1-{len(styles)}): ")) - 1
                    style = styles[s_choice] if 0 <= s_choice < len(styles) else "storytelling"
                    
                    test_single_prompt(custom_product, platform, style)
                else:
                    idx = int(choice) - 1
                    if 0 <= idx < len(products):
                        print("\nSelect platform and style:")
                        for i, p in enumerate(platforms, 1):
                            print(f"{i}. {p}")
                        p_choice = int(input(f"Platform (1-{len(platforms)}): ")) - 1
                        platform = platforms[p_choice] if 0 <= p_choice < len(platforms) else "instagram"
                        
                        for i, s in enumerate(styles, 1):
                            print(f"{i}. {s}")
                        s_choice = int(input(f"Style (1-{len(styles)}): ")) - 1
                        style = styles[s_choice] if 0 <= s_choice < len(styles) else "storytelling"
                        
                        test_single_prompt(products[idx], platform, style)
                    else:
                        print("Invalid selection")
            except ValueError:
                print("Please enter a valid number")
            except KeyboardInterrupt:
                print("\nExiting test")
                break
    else:
        print("No products in database, using custom mode")
        print()
        
        while True:
            try:
                custom_product = {
                    "product_name": input("\nProduct name (or 'q' to quit): ").strip(),
                    "category": "",
                    "description": "",
                    "tags": "",
                    "brand_voice": "",
                    "product_images_count": 1,
                    "scene_images_count": 1,
                    "product_images": [],
                    "scene_images": [],
                    "reference_images": []
                }
                
                if custom_product['product_name'].lower() == 'q':
                    print("Exiting test")
                    break
                
                custom_product['category'] = input("Category: ").strip() or "Baby Products"
                custom_product['description'] = input("Description: ").strip() or "High-quality baby product"
                custom_product['tags'] = input("Tags (comma separated): ").strip() or "baby,high-quality"
                custom_product['brand_voice'] = input("Brand voice: ").strip() or "Professional and Warm"
                
                print("\nSelect platform and style:")
                for i, p in enumerate(platforms, 1):
                    print(f"{i}. {p}")
                p_choice = int(input(f"Platform (1-{len(platforms)}): ")) - 1
                platform = platforms[p_choice] if 0 <= p_choice < len(platforms) else "instagram"
                
                for i, s in enumerate(styles, 1):
                    print(f"{i}. {s}")
                s_choice = int(input(f"Style (1-{len(styles)}): ")) - 1
                style = styles[s_choice] if 0 <= s_choice < len(styles) else "storytelling"
                
                test_single_prompt(custom_product, platform, style)
            except KeyboardInterrupt:
                print("\nExiting test")
                break

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Bebcare Prompt Engine Test Tool")
    parser.add_argument("--quick", action="store_true", help="Run quick non-interactive test")
    parser.add_argument("--product", type=int, default=1, help="Product index (default: 1)")
    parser.add_argument("--platform", default="instagram", help="Platform (default: instagram)")
    parser.add_argument("--style", default="storytelling", help="Style (default: storytelling)")
    args = parser.parse_args()
    
    if args.quick:
        # 非交互式快速测试
        products = get_real_products()
        if products and 0 < args.product <= len(products):
            test_single_prompt(products[args.product - 1], args.platform, args.style)
        else:
            print("No products found or invalid product index")
    else:
        # 交互式测试
        interactive_test()