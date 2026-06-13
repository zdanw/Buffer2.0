import requests
import json
import time
from typing import Dict, List, Optional
from bebcare.config.settings import settings
from bebcare.prompt_builder.prompt_engine import prompt_engine
from bebcare.utils.image_utils import download_image, calculate_average_color, get_color_temperature
import torch

class ContentGenerator:
    def __init__(self):
        self.deepseek_api_key = settings.deepseek_api_key
        self.deepseek_api_url = settings.deepseek_api_url
        self.doubao_api_key = settings.doubao_api_key
        self.doubao_api_url = settings.doubao_api_url
        self.doubao_model_id = settings.doubao_model_id
        
        self.image_prompt_system_prompt = """
You are a professional AI image prompt engineer specializing in baby products.
Your task is to convert product information and dimension options into a detailed, vivid Chinese image description that AI image generators can understand perfectly.

Follow these guidelines:
1. Output ONLY the image prompt, no extra text or explanation
2. Use descriptive language with rich details
3. Include scene, lighting, composition, and style elements
4. Keep it concise (80-150 words)
5. Ensure it's suitable for commercial product photography


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
                print(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)[:100]}...")
                
                if attempt < max_retries - 1:
                    print(f"Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
                    delay *= backoff_factor
        
        print(f"All {max_retries} attempts failed. Last error: {str(last_exception)[:200]}")
        raise last_exception
    
    def _call_deepseek(self, prompt: str, system_prompt: str = None, max_tokens: int = 300) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.deepseek_api_key}"
        }
        
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt or prompt_engine.system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": max_tokens
        }
        
        print(f"DeepSeek API URL: {self.deepseek_api_url}")
        print(f"DeepSeek API Key: {self.deepseek_api_key[:10]}...")
        
        def make_request():
            response = requests.post(self.deepseek_api_url, headers=headers, json=data, timeout=60)
            print(f"DeepSeek API Response Status: {response.status_code}")
            print(f"DeepSeek API Response Text: {response.text[:500]}...")
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
        
        return self._retry_request(make_request, max_retries=3, initial_delay=2.0)
    
    def generate_copywriting(self, product_info: Dict, platform: str) -> str:
        prompt = prompt_engine.build_copywriting_prompt(product_info, platform)
        return self._call_deepseek(prompt, prompt_engine.system_prompt, 500)
    
    def generate_image(self, product_info: Dict, platform: str, 
                       reference_images: List[str] = None, 
                       style_hint: Optional[str] = None,
                       num_candidates: int = 1) -> List[str]:
        use_scene_reference = product_info.get('use_scene_reference', False)
        
        if use_scene_reference:
            positive_prompt = prompt_engine.build_scene_reference_prompt(product_info, platform, style_hint)
        else:
            meta_prompt = prompt_engine.build_image_prompt(product_info, platform, style_hint)
            print(f"Generated meta-prompt for image generation: {meta_prompt[:500]}...")
            
            positive_prompt = self._call_deepseek(meta_prompt, self.image_prompt_system_prompt, 200)
            print(f"Final image prompt after DeepSeek processing: {positive_prompt}")
        
        negative_prompt = prompt_engine.build_negative_prompt()
        
        if reference_images:
            avg_color = calculate_average_color(reference_images[0])
            color_temp = get_color_temperature(avg_color)
            positive_prompt += f", {color_temp} color palette"
        
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
            data["image"] = reference_images[:3]
        
        print(f"Doubao API URL: {self.doubao_api_url}")
        print(f"Doubao API Key: {self.doubao_api_key[:10]}...")
        print(f"Doubao Request Data: {json.dumps(data, indent=2, ensure_ascii=False)[:1000]}...")
        
        def make_doubao_request():
            response = requests.post(self.doubao_api_url, headers=headers, json=data, timeout=120)
            print(f"Doubao API Response Status: {response.status_code}")
            print(f"Doubao API Response Text: {response.text[:1000]}...")
            
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                print(f"Doubao API HTTP Error: {e}")
                raise
            
            result = response.json()
            
            if result.get("error"):
                error_code = result["error"].get("code", "Unknown")
                # 下载超时可以重试
                if "Timeout while downloading" in result["error"].get("message", ""):
                    print("Download timeout detected, will retry...")
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
        
        return self._retry_request(make_doubao_request, max_retries=3, initial_delay=5.0)

content_generator = ContentGenerator()