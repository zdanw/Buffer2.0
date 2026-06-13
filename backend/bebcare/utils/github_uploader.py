import base64
import requests
import time
from bebcare.config.settings import settings
from datetime import datetime
import os

class GitHubUploader:
    def __init__(self):
        self.token = settings.github_token
        self.username = settings.github_username
        self.repo = settings.github_repo
        self.branch = settings.github_branch
        self.base_url = f"https://api.github.com/repos/{self.username}/{self.repo}"
    
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
    
    def get_sha_for_path(self, path):
        url = f"{self.base_url}/contents/{path}"
        headers = {"Authorization": f"token {self.token}"}
        
        def make_request():
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.json()["sha"]
            elif response.status_code == 404:
                return None
            response.raise_for_status()
        
        return self._retry_request(make_request, max_retries=3, initial_delay=2.0)
    
    def upload_file(self, file_content, file_name, directory="images"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = os.path.splitext(file_name)[1]
        new_filename = f"{timestamp}_{os.path.splitext(file_name)[0]}{ext}"
        path = f"{directory}/{new_filename}"
        
        if isinstance(file_content, bytes):
            content = base64.b64encode(file_content).decode("utf-8")
        else:
            content = base64.b64encode(file_content.read()).decode("utf-8")
        
        sha = self.get_sha_for_path(path)
        
        data = {
            "message": f"Upload image: {new_filename}",
            "content": content,
            "branch": self.branch
        }
        
        if sha:
            data["sha"] = sha
        
        url = f"{self.base_url}/contents/{path}"
        headers = {
            "Authorization": f"token {self.token}",
            "Content-Type": "application/json"
        }
        
        def make_request():
            response = requests.put(url, json=data, headers=headers, timeout=60)
            
            if response.status_code in [200, 201]:
                cdn_url = f"https://cdn.jsdelivr.net/gh/{self.username}/{self.repo}@{self.branch}/{path}"
                return cdn_url
            else:
                raise Exception(f"Failed to upload to GitHub: {response.text}")
        
        return self._retry_request(make_request, max_retries=3, initial_delay=2.0)

github_uploader = GitHubUploader()