import logging

logger = logging.getLogger(__name__)

import requests
import time
from typing import Dict, Optional, List
from bebcare.config.settings import settings

PLATFORM_CONFIG = {
    "instagram": {
        "metadata": """metadata: { instagram: { type: post, shouldShareToFeed: true } }""",
        "service_names": ["instagram", "instagram-business", "instagram-personal", "instagram-professional", "instagram-creator"]
    },
    "facebook": {
        "metadata": """metadata: { facebook: { type: post } }""",
        "service_names": ["facebook", "facebook-page", "facebook-group", "facebook-profile", "facebook-business"]
    },
    "tiktok": {
        "metadata": "",
        "service_names": ["tiktok", "tiktok-business", "tiktok-account", "tiktok-pro"]
    },
    "twitter": {
        "metadata": "",
        "service_names": ["twitter", "twitter-x", "x", "twitter-business", "x-business"]
    },
    "linkedin": {
        "metadata": "",
        "service_names": ["linkedin", "linkedin-company", "linkedin-personal", "linkedin-professional"]
    },
    "pinterest": {
        "metadata": "",
        "service_names": ["pinterest", "pinterest-business", "pinterest-pro"]
    },
    "youtube": {
        "metadata": "",
        "service_names": ["youtube", "youtube-channel", "youtube-business"]
    },
    "threads": {
        "metadata": "",
        "service_names": ["threads", "threads-business"]
    },
    "mastodon": {
        "metadata": "",
        "service_names": ["mastodon"]
    }
}


class BufferGraphQLClient:
    """Buffer GraphQL API客户端"""
    
    API_URL = "https://api.buffer.com"
    
    def __init__(self, api_token=None):
        self._api_token = api_token or settings.buffer_api_token
    
    def request(self, query, max_retries=3, initial_delay=1.0):
        headers = {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        data = {"query": query}
        delay = initial_delay
        
        for attempt in range(max_retries):
            try:
                response = requests.post(self.API_URL, headers=headers, json=data, timeout=30)
                result = response.json()
                
                if "errors" in result:
                    error_messages = [error.get("message", "Unknown error") for error in result["errors"]]
                    logger.error('GraphQL Error: %s', ', '.join(error_messages))
                    return None
                    
                return result.get("data")
            except requests.exceptions.ReadTimeout:
                logger.warning('GraphQL request timeout, attempt %s/%s', attempt + 1, max_retries)
                if attempt < max_retries - 1:
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.error('GraphQL request timeout, max retries %s reached', max_retries)
            except requests.exceptions.ConnectionError:
                logger.warning('GraphQL connection failed, attempt %s/%s', attempt + 1, max_retries)
                if attempt < max_retries - 1:
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.error('GraphQL connection failed, max retries %s reached', max_retries)
            except Exception as e:
                logger.exception('GraphQL Request Error: %s', e)
                return None
        
        return None
    
    def fetch_account_info(self):
        query = """
        query {
            account {
                id
                email
                name
                organizations {
                    id
                    name
                }
            }
        }
        """
        data = self.request(query)
        if not data:
            return None
        return data.get("account")
    
    def fetch_channels(self, organization_id):
        query = f"""
        query {{
            channels(input: {{ organizationId: "{organization_id}" }}) {{
                id
                name
                service
                avatar
                isQueuePaused
            }}
        }}
        """
        data = self.request(query)
        if not data:
            return []
        
        channels = []
        for channel in data.get("channels", []):
            channels.append({
                "id": channel.get("id"),
                "name": channel.get("name"),
                "service": channel.get("service"),
                "avatar": channel.get("avatar"),
                "isQueuePaused": channel.get("isQueuePaused"),
                "status": "connected" if not channel.get("isQueuePaused") else "paused"
            })
        
        return channels


class BufferCache:
    """Buffer API响应缓存管理器"""
    
    def __init__(self, ttl=600):
        self._ttl = ttl
        self._account_info = None
        self._account_info_time = 0
        self._channels = {}
        self._channels_time = {}
    
    def get_account_info(self, fetch_func):
        now = time.time()
        
        if self._account_info and (now - self._account_info_time) < self._ttl:
            return self._account_info
        
        account_info = fetch_func()
        
        if account_info:
            self._account_info = account_info
            self._account_info_time = now
        
        return account_info
    
    def get_channels(self, organization_id, fetch_func):
        now = time.time()
        
        if organization_id in self._channels:
            if (now - self._channels_time.get(organization_id, 0)) < self._ttl:
                return self._channels[organization_id]
        
        channels = fetch_func(organization_id)
        
        if channels:
            self._channels[organization_id] = channels
            self._channels_time[organization_id] = now
        
        return channels
    
    def clear(self):
        self._account_info = None
        self._account_info_time = 0
        self._channels = {}
        self._channels_time = {}


class BufferPublishService:
    """Buffer发布服务"""
    
    def __init__(self):
        self._client = BufferGraphQLClient()
        self._cache = BufferCache()
    
    @property
    def client(self):
        return self._client
    
    @property
    def cache(self):
        return self._cache
    
    @staticmethod
    def escape_graphql_string(text):
        if not text:
            return text
        
        text = text.replace('\\', '\\\\')
        text = text.replace('"', '\\"')
        text = text.replace('\n', '\\n')
        text = text.replace('\r', '\\r')
        text = text.replace('\t', '\\t')
        
        return text
    
    def _build_create_post_query(self, channel_id, text, media_url=None, platform_type=None):
        query_params = [
            f'channelId: "{channel_id}"',
            f'text: "{text}"',
            f'schedulingType: automatic',
            f'mode: shareNow'
        ]
        
        if media_url:
            query_params.append(f'assets: [{{ image: {{ url: "{media_url}" }} }}]')
        
        platform_config = PLATFORM_CONFIG.get(platform_type, {})
        metadata = platform_config.get("metadata", "")
        if metadata:
            query_params.append(metadata)
        
        params_str = ", ".join(query_params)
        query = f"""
        mutation {{
            createPost(input: {{ {params_str} }}) {{
                ... on PostActionSuccess {{
                    post {{
                        id
                        text
                        dueAt
                    }}
                }}
                ... on MutationError {{
                    message
                }}
            }}
        }}
        """
        
        return query
    
    def _parse_create_post_result(self, data):
        if not data:
            return None
        
        create_post_result = data.get("createPost")
        
        if not create_post_result:
            return {"status": "failed", "message": "发布失败"}
        
        if "post" in create_post_result:
            post = create_post_result["post"]
            return {
                "status": "success",
                "post": {
                    "id": post.get("id"),
                    "text": post.get("text"),
                    "dueAt": post.get("dueAt", "立即")
                }
            }
        elif "message" in create_post_result:
            return {"status": "failed", "message": create_post_result["message"]}
        
        return {"status": "failed", "message": "未知错误"}
    
    def create_post(self, channel_id, text, media_url=None, platform_type=None):
        text = self.escape_graphql_string(text)
        query = self._build_create_post_query(channel_id, text, media_url, platform_type)
        data = self._client.request(query)
        result = self._parse_create_post_result(data)
        
        if result and result.get("status") == "success" and result.get("post"):
            result["post"]["scheduledAt"] = result["post"].pop("dueAt", None)
        
        return result
    
    def publish_to_platforms(self, text, media_url=None, platforms=None):
        if platforms is None:
            platforms = ["instagram", "tiktok", "facebook"]
        
        account = self._cache.get_account_info(self._client.fetch_account_info)
        if not account:
            logger.error('Unable to fetch Buffer account info')
            return [{"error": "Failed to get account info"}]
        
        orgs = account.get("organizations", [])
        if not orgs:
            logger.error('No Buffer organization found')
            return [{"error": "No organizations found"}]
        
        org_id = orgs[0]["id"]
        channels = self._cache.get_channels(org_id, self._client.fetch_channels)
        
        results = []
        
        for platform in platforms:
            matched = False
            
            platform_config = PLATFORM_CONFIG.get(platform, {})
            service_names = platform_config.get("service_names", [])
            
            for channel in channels:
                service = channel.get("service", "").lower()
                
                if service in service_names:
                    matched = True
                    
                    if channel.get("status") != "connected":
                        results.append({
                            "platform": platform,
                            "channel": channel["name"],
                            "status": "failed",
                            "error": "Channel not connected"
                        })
                        continue
                    
                    result = self.create_post(channel["id"], text, media_url, platform)
                    
                    if result and result.get("status") == "success":
                        results.append({
                            "platform": platform,
                            "channel": channel["name"],
                            "status": "success",
                            "post_id": result["post"].get("id"),
                            "scheduled_at": result["post"].get("scheduledAt")
                        })
                    else:
                        error_msg = result.get("message", "Failed to create post") if result else "Unknown error"
                        results.append({
                            "platform": platform,
                            "channel": channel["name"],
                            "status": "failed",
                            "error": error_msg
                        })
            
            if not matched:
                results.append({
                    "platform": platform,
                    "channel": None,
                    "status": "failed",
                    "error": f"No matching channel found for platform '{platform}'"
                })
        
        return results


class BufferPublisher:
    """兼容层：保留原有接口"""
    
    def __init__(self):
        self._service = BufferPublishService()
    
    def _retry_request(self, func, max_retries=3, initial_delay=2.0, backoff_factor=2.0):
        delay = initial_delay
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                logger.warning('Attempt %s/%s failed: %s...', attempt + 1, max_retries, str(e)[:100])
                
                if attempt < max_retries - 1:
                    logger.info('Retrying in %.2f seconds...', delay)
                    time.sleep(delay)
                    delay *= backoff_factor
        
        logger.error('All %s attempts failed. Last error: %s', max_retries, str(last_exception)[:200])
        raise last_exception
    
    def publish(self, text: str, image_url: Optional[str] = None, 
                platforms: Optional[list] = None) -> Dict:
        results = self._service.publish_to_platforms(text, image_url, platforms)
        
        formatted_results = {}
        for result in results:
            platform = result.get("platform")
            formatted_results[platform] = {
                "success": result.get("status") == "success",
                "channel": result.get("channel"),
                "post_id": result.get("post_id"),
                "error": result.get("error")
            }
        
        return formatted_results

buffer_publisher = BufferPublisher()