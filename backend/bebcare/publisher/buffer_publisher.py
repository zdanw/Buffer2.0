import requests
import time
from typing import Dict, Optional
from bebcare.config.settings import settings

class BufferPublisher:
    def __init__(self):
        self.api_token = settings.buffer_api_token
        self.base_url = "https://api.buffer.com/1"
    
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
    
    def publish(self, text: str, image_url: Optional[str] = None, 
                platforms: Optional[list] = None) -> Dict:
        if platforms is None:
            platforms = ["instagram", "tiktok", "facebook"]
        
        results = {}
        for platform in platforms:
            profile_id = self._get_profile_id(platform)
            if profile_id:
                result = self._publish_to_profile(text, image_url, profile_id)
                results[platform] = result
        
        return results
    
    def _get_profile_id(self, platform: str) -> Optional[str]:
        url = f"{self.base_url}/profiles.json"
        headers = {"Authorization": f"Bearer {self.api_token}"}
        
        def make_request():
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                profiles = response.json()
                for profile in profiles:
                    if profile.get("service").lower() == platform.lower():
                        return profile.get("id")
            elif response.status_code == 401:
                print("Buffer API authentication failed")
                return None
            response.raise_for_status()
        
        return self._retry_request(make_request, max_retries=3, initial_delay=2.0)
    
    def _publish_to_profile(self, text: str, image_url: Optional[str], profile_id: str) -> Dict:
        url = f"{self.base_url}/updates/create.json"
        headers = {"Authorization": f"Bearer {self.api_token}"}
        
        data = {
            "profile_ids[]": profile_id,
            "text": text
        }
        
        if image_url:
            data["media[photo]"] = image_url
        
        def make_request():
            response = requests.post(url, headers=headers, data=data, timeout=60)
            
            if response.status_code in [200, 201]:
                return {"success": True, "data": response.json()}
            elif response.status_code == 401:
                return {"success": False, "error": "Authentication failed"}
            else:
                raise Exception(f"Buffer API error: {response.text}")
        
        try:
            return self._retry_request(make_request, max_retries=3, initial_delay=2.0)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_update_status(self, update_id: str) -> Dict:
        url = f"{self.base_url}/updates/{update_id}.json"
        headers = {"Authorization": f"Bearer {self.api_token}"}
        
        def make_request():
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.json()
            response.raise_for_status()
        
        try:
            return self._retry_request(make_request, max_retries=3, initial_delay=2.0)
        except Exception as e:
            return {"error": str(e)}

buffer_publisher = BufferPublisher()