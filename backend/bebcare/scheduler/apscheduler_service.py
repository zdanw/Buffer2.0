from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.executors.pool import ThreadPoolExecutor
from datetime import datetime
from bebcare.generator.content_generator import content_generator
from bebcare.dedup.deduplication_engine import deduplication_engine
from bebcare.publisher.buffer_publisher import buffer_publisher
from bebcare.models import ScheduledTask, TaskExecution, ManualTaskDraft, Product
from bebcare.utils.reference_selector import select_reference_images
from bebcare.config.settings import settings
from sqlalchemy.orm import Session
from sqlalchemy import func
from bebcare.database import engine
import logging
import threading
import uuid

logger = logging.getLogger(__name__)

class APSchedulerService:
    def __init__(self):
        workers = max(1, settings.scheduler_max_workers)
        executors = {
            'default': ThreadPoolExecutor(max_workers=workers)
        }
        job_defaults = {
            # 同一任务不重叠；错过触发时合并，避免 HF 休眠醒来后堆积爆发
            'max_instances': max(1, settings.scheduler_max_instances),
            'coalesce': True,
            'misfire_grace_time': max(60, settings.scheduler_misfire_grace_seconds),
        }
        self.scheduler = BackgroundScheduler(
            timezone='Asia/Shanghai',
            executors=executors,
            job_defaults=job_defaults
        )
        self.running_tasks = {}
        # 全局并发闸：限制同时进行的生成/发布流水线
        self._job_semaphore = threading.Semaphore(max(1, settings.max_concurrent_jobs))
    
    def start(self):
        self.scheduler.start()
        logger.info(
            "APScheduler started (workers=%s, max_concurrent_jobs=%s, max_instances=%s)",
            settings.scheduler_max_workers,
            settings.max_concurrent_jobs,
            settings.scheduler_max_instances,
        )
        logger.info(f"Scheduler running: {self.scheduler.running}")
        logger.info(f"Scheduler timezone: {self.scheduler.timezone}")

    def reload_enabled_tasks(self):
        """进程启动后从 DB 重载已启用任务，避免重启后 cron 丢失。"""
        session = Session(bind=engine)
        try:
            tasks = session.query(ScheduledTask).filter(ScheduledTask.enabled == True).all()
            loaded = 0
            for task in tasks:
                try:
                    self.add_task(
                        str(task.task_id),
                        task.mode,
                        task.cron,
                        task.target_categories or [],
                        task.target_products or [],
                        task.platforms or [],
                        task.reference_image_count,
                        task.run_count_per_execution,
                        task.generate_image_count,
                        task.generate_copy_count,
                        bool(task.use_scene_reference),
                    )
                    loaded += 1
                except Exception as e:
                    logger.error(
                        "Failed to reload scheduled task %s: %s",
                        task.task_id,
                        e,
                        exc_info=True,
                    )
            logger.info("Reloaded %s enabled scheduled task(s) from database", loaded)
        finally:
            session.close()

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
            replace_existing=True,
            max_instances=max(1, settings.scheduler_max_instances),
            coalesce=True,
            misfire_grace_time=max(60, settings.scheduler_misfire_grace_seconds),
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

        acquired = self._job_semaphore.acquire(timeout=max(0, settings.job_queue_wait_seconds))
        if not acquired:
            logger.error(
                "Task %s skipped: reached max_concurrent_jobs=%s after waiting %ss",
                task_id,
                settings.max_concurrent_jobs,
                settings.job_queue_wait_seconds,
            )
            self._record_skipped_execution(
                task_id,
                f"Skipped: concurrency limit ({settings.max_concurrent_jobs})",
            )
            return

        try:
            if mode == "auto":
                self.execute_auto_task(task_id, target_categories, target_products, platforms,
                                       reference_image_count, run_count_per_execution, use_scene_reference)
            elif mode == "manual":
                self.execute_manual_task(task_id, target_categories, target_products, platforms,
                                         reference_image_count, generate_image_count, 
                                         generate_copy_count, use_scene_reference)
        finally:
            self._job_semaphore.release()

    def _record_skipped_execution(self, task_id, message: str):
        session = Session(bind=engine)
        try:
            execution = TaskExecution(
                execution_id=str(uuid.uuid4()),
                task_id=task_id,
                status="FAILED",
                error_message=message,
            )
            session.add(execution)
            session.commit()
        except Exception as e:
            logger.error("Failed to record skipped execution for %s: %s", task_id, e)
            session.rollback()
        finally:
            session.close()
    
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
                    execution.dimensions = result.get("dimensions")
                    execution.image_prompt = result.get("image_prompt")
                    execution.reference_product_images = result.get("reference_product_images", [])
                    execution.reference_scene_images = result.get("reference_scene_images", [])
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
            
            selected = select_reference_images(
                session, product.product_id, reference_image_count, use_scene_reference
            )
            reference_image_urls = selected["reference_images"]
            reference_product_images = selected["reference_product_images"]
            reference_scene_images = selected["reference_scene_images"]
            use_scene_reference = selected["use_scene_reference"]
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
                    copywriting = content_generator.generate_copywriting(
                        product_info, platforms[0] if platforms else "instagram", db=session
                    )
                    copywritings.append(copywriting)
                    logger.info(f"Generated copywriting {i+1}/{generate_copy_count}: {copywriting[:100]}...")
                except Exception as e:
                    logger.error(
                        "Failed to generate copywriting %s/%s for task %s: %s — aborting manual run (no mock)",
                        i + 1,
                        generate_copy_count,
                        task_id,
                        e,
                        exc_info=True,
                    )
                    raise

            images = []
            dimensions_list = []
            image_prompts_list = []
            for i in range(generate_image_count):
                try:
                    image_result = content_generator.generate_image(
                        product_info,
                        platforms[0] if platforms else "instagram",
                        reference_image_urls,
                        db=session,
                    )
                    image_urls = image_result.get("image_urls") if isinstance(image_result, dict) else image_result
                    if not image_urls:
                        raise Exception("Image generation returned no URLs")
                    images.append(image_urls[0])
                    dimensions_list.append(
                        image_result.get("dimensions") if isinstance(image_result, dict) else None
                    )
                    image_prompts_list.append(
                        image_result.get("image_prompt") if isinstance(image_result, dict) else None
                    )
                    logger.info(f"Generated image {i+1}/{generate_image_count}: {image_urls[0]}")
                except Exception as e:
                    logger.error(
                        "Failed to generate image %s/%s for task %s: %s — aborting manual run (no mock)",
                        i + 1,
                        generate_image_count,
                        task_id,
                        e,
                        exc_info=True,
                    )
                    raise

            if not copywritings or not images:
                raise Exception("Manual task produced empty copywritings or images; draft not saved")
            
            draft = ManualTaskDraft(
                draft_id=str(uuid.uuid4()),
                task_id=task_id,
                product_id=str(product.product_id),
                images=images,
                copywritings=copywritings,
                dimensions=dimensions_list,
                image_prompts=image_prompts_list,
                reference_product_images=reference_product_images,
                reference_scene_images=reference_scene_images,
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
        
        selected = select_reference_images(
            session, product.product_id, reference_image_count, use_scene_reference
        )
        reference_image_urls = selected["reference_images"]
        reference_product_images = selected["reference_product_images"]
        reference_scene_images = selected["reference_scene_images"]
        use_scene_reference = selected["use_scene_reference"]
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
        
        copywriting = content_generator.generate_copywriting(product_info, platforms[0] if platforms else "instagram", db=session)
        logger.info(f"Generated copywriting: {copywriting[:100]}...")

        image_result = content_generator.generate_image(
            product_info, platforms[0] if platforms else "instagram", reference_image_urls, db=session
        )
        image_urls = image_result.get("image_urls") if isinstance(image_result, dict) else image_result
        dimensions = image_result.get("dimensions") if isinstance(image_result, dict) else None
        image_prompt = image_result.get("image_prompt") if isinstance(image_result, dict) else None
        if not image_urls:
            raise Exception("Auto task image generation returned no URLs; publish aborted")
        logger.info(f"Generated images: {image_urls}")

        generated_images = []
        published_platforms = []

        similarity = deduplication_engine.calculate_text_image_match(copywriting, image_urls[0])
        if similarity is None:
            logger.info("Text-image match skipped (CLIP disabled)")
        else:
            logger.info(f"Text-image match score: {similarity:.2f}")
            if similarity < 0.2:
                logger.warning(
                    "Text-image match score %.2f is too low; skipping publish for task %s",
                    similarity,
                    task_id,
                )
                return {
                    "images": [],
                    "platforms": [],
                    "copywriting": copywriting,
                    "dimensions": dimensions,
                    "image_prompt": image_prompt,
                    "reference_product_images": reference_product_images,
                    "reference_scene_images": reference_scene_images,
                }

        # generate_image already persists to CDN
        cdn_url = image_urls[0]
        generated_images.append(cdn_url)

        publish_result = buffer_publisher.publish(copywriting, cdn_url, platforms)
        logger.info(f"Publish result: {publish_result}")

        success_platforms = []
        for platform, result in publish_result.items():
            if result.get("success"):
                success_platforms.append(platform)
        published_platforms = success_platforms

        if not published_platforms:
            raise Exception(f"Buffer publish failed for all platforms: {publish_result}")

        return {
            "images": generated_images,
            "platforms": published_platforms,
            "copywriting": copywriting,
            "dimensions": dimensions,
            "image_prompt": image_prompt,
            "reference_product_images": reference_product_images,
            "reference_scene_images": reference_scene_images,
        }

scheduler_service = APSchedulerService()
