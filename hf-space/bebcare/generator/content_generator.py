import requests
import json
import time
from typing import Dict, List, Optional
from bebcare.config.settings import settings
from bebcare.prompt_builder.prompt_engine import prompt_engine
from bebcare.utils.image_utils import persist_image_url_to_cdn

class ContentGenerator:
    def __init__(self):
        self.deepseek_api_key = settings.deepseek_api_key
        self.deepseek_api_url = settings.deepseek_api_url
        self.doubao_api_key = settings.doubao_api_key
        self.doubao_api_url = settings.doubao_api_url
        self.doubao_model_id = settings.doubao_model_id
        
        self.image_prompt_system_prompt = """
你是一位专业的AI图像提示词工程师，专注于婴儿产品领域。
你的任务是将产品信息和维度选项转换为详细、生动、富有感染力的中文图像描述，让AI图像生成器能够完美理解并生成高质量图片。

遵循以下指南：
1. 仅输出图像提示词，不要额外文本或解释
2. 使用丰富细腻的描述性语言，包含大量感官细节和具体形容词
3. 将场景、光线、构图、风格、画质、细节道具等元素自然融合，形成连贯的叙事
4. 注重光影层次：描述光线的方向、质感、色温，以及光影如何塑造产品形态和氛围
5. 强调材质表现：描述产品的材质质感（如哑光、细腻、圆润、柔软等），以及材质之间的对比
6. 营造情感氛围：通过场景和细节传递宁静、安全、温暖、陪伴等婴儿产品特有的情感
7. 采用生活方式叙事：描述产品在真实生活场景中的使用状态，增强画面的故事感和代入感
8. 确保适合商业产品摄影，同时具备艺术感染力和视觉冲击力
9. 描述要有层次感：从前景到背景，从主体到细节，逐步展开，形成完整的画面构图
10. 使用精确的色彩描述：避免笼统的颜色词，使用具体的色调描述（如米白色针织棉布、马卡龙色系、温暖金色等）
"""
    
    def _retry_request(self, func, max_retries=3, initial_delay=2.0, backoff_factor=2.0):
        """带指数退避的通用重试函数"""
        delay = initial_delay
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    time.sleep(delay)
                    delay *= backoff_factor
        
        raise last_exception
    
    def _call_deepseek(self, prompt: str, system_prompt: str = None, max_tokens: int = 300) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.deepseek_api_key}"
        }

        def request_once(token_limit: int):
            data = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt or prompt_engine.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": token_limit
            }
            response = requests.post(self.deepseek_api_url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            choice = response.json()["choices"][0]
            return choice["message"]["content"].strip(), choice.get("finish_reason")

        def make_request():
            content, finish_reason = request_once(max_tokens)
            # finish_reason=length 表示因 max_tokens 被截断，再抬高一次上限重试
            retry_limit = max_tokens
            if finish_reason == "length":
                retry_limit = min(max(max_tokens * 2, 1024), 4096)
                if retry_limit > max_tokens:
                    content, finish_reason = request_once(retry_limit)
            if finish_reason == "length":
                raise Exception(f"DeepSeek output truncated after max_tokens={retry_limit}")
            return content

        return self._retry_request(make_request, max_retries=3, initial_delay=2.0)
    
    def generate_copywriting(self, product_info: Dict, platform: str, db=None) -> str:
        prompt = prompt_engine.build_copywriting_prompt(product_info, platform, db)
        return self._call_deepseek(prompt, prompt_engine.system_prompt, 500)
    
    def generate_image(self, product_info: Dict, platform: str, 
                       reference_images: List[str] = None, 
                       style_hint: Optional[str] = None,
                       num_candidates: int = 1,
                       db=None) -> Dict:
        use_scene_reference = product_info.get('use_scene_reference', False)
        
        selected_dimensions = None
        image_prompt = None
        
        if use_scene_reference:
            positive_prompt = prompt_engine.build_scene_reference_prompt(product_info, platform, style_hint, db)
            image_prompt = positive_prompt
        else:
            image_prompt_result = prompt_engine.build_image_prompt(product_info, platform, style_hint, db)
            meta_prompt = image_prompt_result["prompt"]
            selected_dimensions = image_prompt_result.get("dimensions", None)
            
            # 详细中文图像描述通常远超 200 tokens；1024 覆盖完整提示词
            positive_prompt = self._call_deepseek(meta_prompt, self.image_prompt_system_prompt, 1024)
            image_prompt = positive_prompt
        
        negative_prompt = prompt_engine.build_negative_prompt()
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.doubao_api_key}",
            "X-Ark-Sdk-Version": "v1.0.0"
        }
        
        data = {
            "model": self.doubao_model_id,
            "prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "size": "2048x2048",
            "sequential_image_generation": "disabled",
            "response_format": "url",
            "watermark": False
        }
        
        if reference_images and len(reference_images) > 0:
            data["image"] = reference_images
        
        def make_doubao_request():
            response = requests.post(self.doubao_api_url, headers=headers, json=data, timeout=120)
            
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                raise
            
            result = response.json()
            
            if result.get("error"):
                error_code = result["error"].get("code", "Unknown")
                if "Timeout while downloading" in result["error"].get("message", ""):
                    raise Exception(f"Download timeout: {result['error']['message']}")
                raise Exception(f"Image generation failed: {result['error'].get('message', 'Unknown error')}")
            
            image_urls = []
            if result.get("data"):
                for item in result["data"]:
                    if isinstance(item, dict) and "url" in item:
                        image_urls.append(item["url"])
            
            if not image_urls:
                raise Exception("No images generated")
            
            return image_urls
        
        try:
            image_urls = self._retry_request(make_doubao_request, max_retries=3, initial_delay=5.0)
        except Exception as e:
            raise Exception(f"Image generation failed after retries: {e}") from e

        if not image_urls:
            raise Exception("No images generated")

        product_id = product_info.get("product_id", "gen")
        cdn_urls = []
        for i, url in enumerate(image_urls):
            file_name = f"{product_id}_{int(time.time())}_{i}.jpg"
            cdn_urls.append(persist_image_url_to_cdn(url, file_name))

        return {
            "image_urls": cdn_urls,
            "dimensions": selected_dimensions,
            "image_prompt": image_prompt
        }

content_generator = ContentGenerator()