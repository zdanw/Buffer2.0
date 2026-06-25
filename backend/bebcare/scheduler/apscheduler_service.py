from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from bebcare.generator.content_generator import content_generator
from bebcare.dedup.deduplication_engine import deduplication_engine
from bebcare.utils.github_uploader import github_uploader
from bebcare.publisher.buffer_publisher import buffer_publisher
from bebcare.utils.image_utils import download_image
from bebcare.models import ScheduledTask, TaskExecution, ManualTaskDraft, Product, ProductImage
from sqlalchemy.orm import Session
from sqlalchemy import func
from bebcare.database import engine
import logging
import pytz
import uuid
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
    
    def add_task(self, task_id, mode, cron_expression, target_categories, target_products, platforms,
                 reference_image_count, run_count_per_execution, generate_image_count, generate_copy_count,
                 use_scene_reference=False):
        trigger = CronTrigger.from_crontab(cron_expression, timezone='Asia/Shanghai')
        
        job = self.scheduler.add_job(
            self.execute_task_by_mode,
            trigger=trigger,
            id=str(task_id),
            args=[task_id, mode, target_categories, target_products, platforms, reference_image_count, 
                  run_count_per_execution, generate_image_count, generate_copy_count, use_scene_reference],
            replace_existing=True
        )
        
        self.running_tasks[str(task_id)] = job
        next_run = job.next_run_time
        logger.info(f"Scheduled task {task_id} ({mode} mode) added, next run at: {next_run}")
        
        session = Session(bind=engine)
        try:
            task = session.query(ScheduledTask).filter(ScheduledTask.task_id == task_id).first()
            if task:
                task.next_run_at = next_run
                session.commit()
        finally:
            session.close()
            
        return job
    
    def remove_task(self, task_id):
        if str(task_id) in self.running_tasks:
            self.scheduler.remove_job(str(task_id))
            del self.running_tasks[str(task_id)]
            logger.info(f"Scheduled task {task_id} removed")
    
    def update_task(self, task_id, mode, cron_expression, target_categories, target_products, platforms,
                    reference_image_count, run_count_per_execution, generate_image_count, generate_copy_count,
                    use_scene_reference=False):
        self.remove_task(task_id)
        return self.add_task(task_id, mode, cron_expression, target_categories, target_products, platforms,
                             reference_image_count, run_count_per_execution, generate_image_count, 
                             generate_copy_count, use_scene_reference)
    
    def toggle_task(self, task_id, enabled):
        if str(task_id) in self.running_tasks:
            job = self.running_tasks[str(task_id)]
            if enabled:
                job.resume()
            else:
                job.pause()
            logger.info(f"Task {task_id} {'enabled' if enabled else 'disabled'}")
    
    def execute_task_by_mode(self, task_id, mode, target_categories, target_products, platforms,
                             reference_image_count, run_count_per_execution, generate_image_count, 
                             generate_copy_count, use_scene_reference=False):
        logger.info(f"Executing task {task_id} in {mode} mode at {datetime.now()}")
        
        if mode == "auto":
            self.execute_auto_task(task_id, target_categories, target_products, platforms,
                                   reference_image_count, run_count_per_execution, use_scene_reference)
        elif mode == "manual":
            self.execute_manual_task(task_id, target_categories, target_products, platforms,
                                     reference_image_count, generate_image_count, 
                                     generate_copy_count, use_scene_reference)
    
    def execute_auto_task(self, task_id, target_categories, target_products, platforms,
                          reference_image_count, run_count_per_execution, use_scene_reference=False):
        logger.info(f"Executing auto task {task_id} at {datetime.now()}")
        
        session = Session(bind=engine)
        try:
            for _ in range(run_count_per_execution):
                execution_id = str(uuid.uuid4())
                execution = TaskExecution(
                    execution_id=execution_id,
                    task_id=task_id,
                    status="RUNNING"
                )
                session.add(execution)
                session.commit()
                
                try:
                    result = self._execute_single_run(session, task_id, target_categories, target_products, platforms,
                                                      reference_image_count, use_scene_reference)
                    
                    execution.status = "SUCCESS"
                    execution.generated_images = result.get("images", [])
                    execution.published_platforms = result.get("platforms", [])
                    execution.copywriting = result.get("copywriting", "")
                except Exception as e:
                    execution.status = "FAILED"
                    execution.error_message = str(e)
                    logger.error(f"Error executing task workflow: {str(e)}", exc_info=True)
                
                session.commit()
            
            task = session.query(ScheduledTask).filter(ScheduledTask.task_id == task_id).first()
            if task:
                task.last_run_at = datetime.now()
                if str(task_id) in self.running_tasks:
                    job = self.running_tasks[str(task_id)]
                    task.next_run_at = job.next_run_time
                session.commit()
                
        finally:
            session.close()
    
    def execute_manual_task(self, task_id, target_categories, target_products, platforms,
                            reference_image_count, generate_image_count, generate_copy_count,
                            use_scene_reference=False):
        logger.info(f"Executing manual task {task_id} at {datetime.now()}")
        
        session = Session(bind=engine)
        try:
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
            logger.info(f"Using reference images ({len(reference_image_urls)}): {reference_image_urls}")
            
            product_info = {
                "product_id": str(product.product_id),
                "product_name": product.product_name,
                "category": product.category,
                "description": product.description,
                "selling_points": product.selling_points,
                "brand_voice": product.brand_voice,
                "reference_images": reference_image_urls,
                "platform": platforms[0] if platforms else "instagram",
                "use_scene_reference": use_scene_reference,
            }
            
            copywritings = []
            for i in range(generate_copy_count):
                try:
                    copywriting = content_generator.generate_copywriting(product_info, platforms[0] if platforms else "instagram")
                    copywritings.append(copywriting)
                    logger.info(f"Generated copywriting {i+1}/{generate_copy_count}: {copywriting[:100]}...")
                except Exception as e:
                    logger.error(f"Failed to generate copywriting {i+1}: {str(e)}")
                    mock_text = f"Discover the endless possibilities of {product.product_name}! This product brings a whole new experience to your life. Whether for everyday use or special occasions, {product.product_name} delivers perfect performance. Experience it now and embrace a better life! #technology #lifestyle #quality"
                    copywritings.append(mock_text)
            
            images = []
            for i in range(generate_image_count):
                try:
                    image_urls = content_generator.generate_image(product_info, platforms[0] if platforms else "instagram", reference_image_urls)
                    if image_urls:
                        images.append(image_urls[0])
                        logger.info(f"Generated image {i+1}/{generate_image_count}: {image_urls[0]}")
                except Exception as e:
                    logger.error(f"Failed to generate image {i+1}: {str(e)}")
                    images.append(f"https://picsum.photos/1024/1024?random={i+1}")
            
            draft = ManualTaskDraft(
                draft_id=str(uuid.uuid4()),
                task_id=task_id,
                product_id=str(product.product_id),
                images=images,
                copywritings=copywritings,
                status="pending"
            )
            session.add(draft)
            session.commit()
            
            logger.info(f"Manual task {task_id} completed, draft saved with {len(images)} images and {len(copywritings)} copywritings")
            
            task = session.query(ScheduledTask).filter(ScheduledTask.task_id == task_id).first()
            if task:
                task.last_run_at = datetime.now()
                if str(task_id) in self.running_tasks:
                    job = self.running_tasks[str(task_id)]
                    task.next_run_at = job.next_run_time
                session.commit()
                
        except Exception as e:
            logger.error(f"Error executing manual task {task_id}: {str(e)}", exc_info=True)
        finally:
            session.close()
    
    def _execute_single_run(self, session, task_id, target_categories, target_products, platforms,
                            reference_image_count, use_scene_reference=False):
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
            return {"images": [], "platforms": [], "copywriting": ""}
        
        reference_images = session.query(ProductImage).filter(
            ProductImage.product_id == product.product_id
        ).order_by(func.random()).limit(reference_image_count).all()
        
        reference_image_urls = [img.cdn_url for img in reference_images]
        logger.info(f"Using reference images ({len(reference_image_urls)}): {reference_image_urls}")
        logger.info(f"Scene reference mode: {use_scene_reference}")
        
        product_info = {
            "product_id": str(product.product_id),
            "product_name": product.product_name,
            "category": product.category,
            "description": product.description,
            "selling_points": product.selling_points,
            "brand_voice": product.brand_voice,
            "reference_images": reference_image_urls,
            "platform": platforms[0] if platforms else "instagram",
            "use_scene_reference": use_scene_reference,
        }
        
        copywriting = content_generator.generate_copywriting(product_info, platforms[0] if platforms else "instagram")
        logger.info(f"Generated copywriting: {copywriting[:100]}...")
        
        image_urls = content_generator.generate_image(product_info, platforms[0] if platforms else "instagram", reference_image_urls)
        logger.info(f"Generated images: {image_urls}")
        
        generated_images = []
        published_platforms = []
        
        if image_urls:
            similarity = deduplication_engine.calculate_text_image_match(copywriting, image_urls[0])
            logger.info(f"Text-image match score: {similarity:.2f}")
            if similarity < 0.2:
                logger.info(f"Text-image match score {similarity:.2f} is too low, skipping")
                return {"images": [], "platforms": [], "copywriting": copywriting}
            
            image = download_image(image_urls[0])
            if image:
                buffer = BytesIO()
                image.save(buffer, format='JPEG')
                buffer.seek(0)
                cdn_url = github_uploader.upload_file(buffer, f"{product.product_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
                logger.info(f"Uploaded to CDN: {cdn_url}")
                generated_images.append(cdn_url)
                
                publish_result = buffer_publisher.publish(copywriting, cdn_url, platforms)
                logger.info(f"Publish result: {publish_result}")
                
                success_platforms = []
                for platform, result in publish_result.items():
                    if result.get("success"):
                        success_platforms.append(platform)
                published_platforms = success_platforms
        
        return {"images": generated_images, "platforms": published_platforms, "copywriting": copywriting}

scheduler_service = APSchedulerService()
