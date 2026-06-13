from celery import Celery
from celery.exceptions import MaxRetriesExceededError
from bebcare.config.settings import settings
from bebcare.generator.content_generator import content_generator
from bebcare.dedup.deduplication_engine import deduplication_engine
from bebcare.utils.github_uploader import github_uploader
from bebcare.publisher.buffer_publisher import buffer_publisher
from bebcare.utils.image_utils import download_image
import logging

logger = logging.getLogger(__name__)

celery_app = Celery(
    "bebcare_tasks",
    broker=settings.redis_url,
    backend=settings.redis_url
)

celery_app.conf.task_routes = {
    'bebcare.tasks.content_tasks.*': {'queue': 'content'}
}

celery_app.conf.task_retry_backoff = 3
celery_app.conf.task_retry_backoff_max = 30
celery_app.conf.task_max_retries = 3

@celery_app.task(bind=True)
def generate_copywriting_task(self, product_info):
    try:
        platform = product_info.get('platform', 'instagram')
        copywriting = content_generator.generate_copywriting(product_info, platform)
        return {"success": True, "copywriting": copywriting}
    except Exception as e:
        logger.error(f"Copywriting generation failed: {str(e)}")
        raise self.retry(exc=e)

@celery_app.task(bind=True)
def generate_image_task(self, product_info):
    try:
        platform = product_info.get('platform', 'instagram')
        reference_images = product_info.get('reference_images', [])
        style_hint = product_info.get('style_hint')
        
        images = content_generator.generate_image(
            product_info, platform, reference_images, style_hint, num_candidates=4
        )
        
        return {"success": True, "images": images}
    except Exception as e:
        logger.error(f"Image generation failed: {str(e)}")
        raise self.retry(exc=e)

@celery_app.task(bind=True)
def deduplicate_task(self, image_urls, product_id=None):
    try:
        valid_images = []
        for image_url in image_urls:
            is_duplicate_phash, _ = deduplication_engine.check_image_duplicate(image_url, product_id)
            is_duplicate_clip, _ = deduplication_engine.check_image_similarity(image_url, product_id)
            
            if not is_duplicate_phash and not is_duplicate_clip:
                valid_images.append(image_url)
        
        if not valid_images:
            return {"success": False, "error": "All images are duplicates"}
        
        return {"success": True, "images": valid_images}
    except Exception as e:
        logger.error(f"Deduplication failed: {str(e)}")
        raise self.retry(exc=e)

@celery_app.task(bind=True)
def upload_to_cdn_task(self, image_url, file_name):
    try:
        image = download_image(image_url)
        import io
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG')
        buffer.seek(0)
        
        cdn_url = github_uploader.upload_file(buffer, file_name)
        return {"success": True, "cdn_url": cdn_url}
    except Exception as e:
        logger.error(f"CDN upload failed: {str(e)}")
        raise self.retry(exc=e)

@celery_app.task(bind=True)
def publish_to_buffer_task(self, text, cdn_url, platforms):
    try:
        result = buffer_publisher.publish(text, cdn_url, platforms)
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Buffer publish failed: {str(e)}")
        raise self.retry(exc=e)