import logging

logger = logging.getLogger(__name__)

from PIL import Image
import imagehash
import requests
import time
from io import BytesIO

def _retry_request(func, max_retries=3, initial_delay=2.0, backoff_factor=2.0):
    """带指数退避的通用重试函数"""
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

def calculate_phash(image):
    if isinstance(image, str):
        def download_func():
            response = requests.get(image, timeout=30)
            response.raise_for_status()
            return Image.open(BytesIO(response.content))
        
        image = _retry_request(download_func, max_retries=3, initial_delay=2.0)
    
    phash = imagehash.phash(image)
    return str(phash)

def hamming_distance(hash1, hash2):
    if len(hash1) != len(hash2):
        return float('inf')
    return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))

def get_image_dimensions(image):
    if isinstance(image, str):
        def download_func():
            response = requests.get(image, timeout=30)
            response.raise_for_status()
            return Image.open(BytesIO(response.content))
        
        image = _retry_request(download_func, max_retries=3, initial_delay=2.0)
    
    return image.size

def download_image(url):
    def download_func():
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    
    return _retry_request(download_func, max_retries=3, initial_delay=2.0)

def calculate_average_color(image):
    if isinstance(image, str):
        image = download_image(image)
    image = image.resize((1, 1)).convert('RGB')
    r, g, b = image.getpixel((0, 0))
    return (r / 255, g / 255, b / 255)

def get_color_temperature(avg_color):
    r, g, b = avg_color
    if r > g and r > b:
        return "warm"
    elif b > g and b > r:
        return "cool"
    else:
        return "neutral"