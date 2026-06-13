from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from bebcare.generator.content_generator import content_generator
from bebcare.dedup.deduplication_engine import deduplication_engine
from bebcare.utils.github_uploader import github_uploader
from bebcare.publisher.buffer_publisher import buffer_publisher
from bebcare.utils.image_utils import download_image
from bebcare.models import ScheduledTask, Product, ProductImage
from sqlalchemy.orm import Session
from sqlalchemy import func
from bebcare.database import engine
import logging
import pytz
from io import BytesIO

logger = logging.getLogger(__name__)

class APSchedulerService:
    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone='Asia/Shanghai')
        self.running_tasks = {}
    
    def start(self):
        self.scheduler.start()
        logger.info("APScheduler started")
        logger.info(f"Scheduler running: {self.scheduler.running}")
        logger.info(f"Scheduler timezone: {self.scheduler.timezone}")
    
    def stop(self):
        self.scheduler.shutdown()
        logger.info("APScheduler stopped")
    
    def add_task(self, task_id, cron_expression, target_categories, target_products, platforms,
                 reference_image_count, run_count_per_execution):
        trigger = CronTrigger.from_crontab(cron_expression, timezone='Asia/Shanghai')
        
        job = self.scheduler.add_job(
            self.execute_scheduled_task,
            trigger=trigger,
            id=str(task_id),
            args=[task_id, target_categories, target_products, platforms, reference_image_count, 
                  run_count_per_execution],
            replace_existing=True
        )
        
        self.running_tasks[str(task_id)] = job
        next_run = job.next_run_time
        logger.info(f"Scheduled task {task_id} added, next run at: {next_run}")
        return job
    
    def remove_task(self, task_id):
        if str(task_id) in self.running_tasks:
            self.scheduler.remove_job(str(task_id))
            del self.running_tasks[str(task_id)]
            logger.info(f"Scheduled task {task_id} removed")
    
    def update_task(self, task_id, cron_expression, target_categories, target_products, platforms,
                    reference_image_count, run_count_per_execution):
        self.remove_task(task_id)
        return self.add_task(task_id, cron_expression, target_categories, target_products, platforms,
                             reference_image_count, run_count_per_execution)
    
    def toggle_task(self, task_id, enabled):
        if str(task_id) in self.running_tasks:
            job = self.running_tasks[str(task_id)]
            if enabled:
                job.resume()
            else:
                job.pause()
            logger.info(f"Task {task_id} {'enabled' if enabled else 'disabled'}")
    
    def execute_scheduled_task(self, task_id, target_categories, target_products, platforms,
                               reference_image_count, run_count_per_execution):
        logger.info(f"Executing scheduled task {task_id} at {datetime.now()}")
        
        try:
            session = Session(bind=engine)
            try:
                products = session.query(ScheduledTask).filter(
                    ScheduledTask.task_id == task_id
                ).first()
                
                if not products:
                    logger.error(f"No products found for task {task_id}")
                    return
                
                for _ in range(run_count_per_execution):
                    self._execute_single_run(session, task_id, target_categories, target_products, platforms,
                                            reference_image_count)
            finally:
                session.close()
        
        except Exception as e:
            logger.error(f"Error executing scheduled task {task_id}: {str(e)}", exc_info=True)
    
    def _execute_single_run(self, session, task_id, target_categories, target_products, platforms,
                            reference_image_count):
        if target_products and len(target_products) > 0:
            product = session.query(Product).filter(
                Product.product_id.in_(target_products)
            ).order_by(func.random()).first()
        else:
            product = session.query(Product).filter(
                Product.category.in_(target_categories)
            ).order_by(func.random()).first()
        
        if not product:
            logger.error("No product found in target categories or products")
            return
        
        reference_images = session.query(ProductImage).filter(
            ProductImage.product_id == product.product_id
        ).order_by(func.random()).limit(reference_image_count).all()
        
        reference_image_urls = [img.cdn_url for img in reference_images]
        
        product_info = {
            "product_id": str(product.product_id),
            "product_name": product.product_name,
            "category": product.category,
            "description": product.description,
            "tags": product.tags,
            "brand_voice": product.brand_voice,
            "reference_images": reference_image_urls,
            "platform": platforms[0] if platforms else "instagram",
        }
        
        try:
            copywriting = content_generator.generate_copywriting(product_info, platforms[0] if platforms else "instagram")
            logger.info(f"Generated copywriting: {copywriting[:100]}...")
            
            image_urls = content_generator.generate_image(product_info, platforms[0] if platforms else "instagram", reference_image_urls)
            logger.info(f"Generated images: {image_urls}")
            
            if image_urls:
                similarity = deduplication_engine.calculate_text_image_match(copywriting, image_urls[0])
                logger.info(f"Text-image match score: {similarity:.2f}")
                if similarity < 0.2:
                    logger.info(f"Text-image match score {similarity:.2f} is too low, skipping")
                    return
                
                image = download_image(image_urls[0])
                if image:
                    buffer = BytesIO()
                    image.save(buffer, format='JPEG')
                    buffer.seek(0)
                    cdn_url = github_uploader.upload_file(buffer, f"{product.product_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
                    logger.info(f"Uploaded to CDN: {cdn_url}")
                    
                    publish_result = buffer_publisher.publish(copywriting, cdn_url, platforms)
                    logger.info(f"Publish result: {publish_result}")
        except Exception as e:
            logger.error(f"Error executing task workflow: {str(e)}", exc_info=True)

scheduler_service = APSchedulerService()