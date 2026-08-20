from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.executors.pool import ThreadPoolExecutor
from datetime import datetime
from types import SimpleNamespace
from bebcare.generator.content_generator import content_generator
from bebcare.dedup.deduplication_engine import deduplication_engine
from bebcare.publisher.buffer_publisher import buffer_publisher
from bebcare.models import ScheduledTask, TaskExecution, ManualTaskDraft, Product
from bebcare.utils.reference_selector import select_reference_images
from bebcare.services.brand_context import enrich_product_info
from bebcare.services.buffer_account_service import (
    resolve_buffer_api_token,
    BufferAccountUnavailable,
)
from bebcare.services.ownership import stamp_owner
from bebcare.config.settings import settings
from bebcare.services.generate_task_store import (
    create_generate_task,
    update_generate_task,
)
from bebcare.services.credit_grant_service import CreditError, reserve_one
from sqlalchemy.orm import Session
from bebcare.database import engine
import logging
import threading
import uuid

logger = logging.getLogger(__name__)


def _run_platform_image_generation(owner_user_id: str, mode: str | None, generate_fn):
    """Reserve one platform credit around a single image generation when mode=platform."""
    if mode != "platform":
        return generate_fn()

    gen_task_id = str(uuid.uuid4())
    create_generate_task(gen_task_id, status="PENDING", owner_user_id=owner_user_id)
    session = Session(bind=engine)
    try:
        reserve_one(session, user_id=owner_user_id, generate_task_id=gen_task_id)
        session.commit()
    except CreditError as exc:
        session.rollback()
        update_generate_task(
            gen_task_id,
            status="FAILURE",
            set_result=True,
            result={"error": str(exc)},
        )
        raise Exception(
            "平台出图额度不足，调度任务无法使用平台供应商出图（不会静默切换到 BYOK）"
        ) from exc
    finally:
        session.close()

    try:
        result = generate_fn()
        update_generate_task(gen_task_id, status="SUCCESS")
        return result
    except Exception:
        update_generate_task(
            gen_task_id,
            status="FAILURE",
            set_result=True,
            result={"error": "scheduler image generation failed"},
        )
        raise


def products_for_task(session, task) -> list:
    """Products targeted by this scheduled task, limited to the task owner."""
    target_products = task.target_products or []
    target_categories = task.target_categories or []
    owner_id = task.owner_user_id

    if target_products:
        found = (
            session.query(Product)
            .filter(
                Product.product_id.in_(target_products),
                Product.owner_user_id == owner_id,
            )
            .all()
        )
        by_id = {str(p.product_id): p for p in found}
        return [by_id[str(pid)] for pid in target_products if str(pid) in by_id]
    if target_categories:
        return (
            session.query(Product)
            .filter(
                Product.category.in_(target_categories),
                Product.owner_user_id == owner_id,
            )
            .order_by(Product.product_name)
            .all()
        )
    return []


def _task_owner(task):
    return SimpleNamespace(user_id=task.owner_user_id)


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
            task = session.query(ScheduledTask).filter(ScheduledTask.task_id == task_id).first()
            if not task:
                logger.error("Cannot record skipped execution; task %s not found", task_id)
                return
            execution = TaskExecution(
                execution_id=str(uuid.uuid4()),
                task_id=task_id,
                status="FAILED",
                error_message=message,
            )
            stamp_owner(execution, _task_owner(task))
            session.add(execution)
            session.commit()
        except Exception as e:
            logger.error("Failed to record skipped execution for %s: %s", task_id, e)
            session.rollback()
        finally:
            session.close()

    def _prepare_product_context(
        self, session, product, task_id, reference_image_count, use_scene_reference, platforms
    ):
        selected = select_reference_images(
            session, product.product_id, reference_image_count, use_scene_reference
        )
        reference_image_urls = selected["reference_images"]
        effective_scene = selected["use_scene_reference"]
        logger.info(
            "Product %s reference images (%s): %s",
            product.product_id,
            len(reference_image_urls),
            reference_image_urls,
        )
        logger.info("Scene reference mode: %s", effective_scene)

        task_cfg = session.query(ScheduledTask).filter(ScheduledTask.task_id == task_id).first()
        product_id_str = str(product.product_id)
        base_info = {
            "product_id": product_id_str,
            "product_name": product.product_name,
            "category": product.category,
            "description": product.description,
            "selling_points": product.selling_points,
            "brand_voice": product.brand_voice,
            "reference_images": reference_image_urls,
            "reference_product_images": selected["reference_product_images"],
            "reference_scene_images": selected["reference_scene_images"],
            "platform": platforms[0] if platforms else "instagram",
            "use_scene_reference": effective_scene,
            "use_vision_image_prompt": bool(
                getattr(task_cfg, "use_vision_image_prompt", False)
            )
            if task_cfg
            else False,
        }
        product_info = enrich_product_info(session, product, base_info)
        owner_user_id = (
            task_cfg.owner_user_id if task_cfg else product.owner_user_id
        )
        provider_mode = (
            getattr(task_cfg, "image_provider_mode", None) if task_cfg else None
        ) or "byok"
        product_info["owner_user_id"] = owner_user_id
        product_info["image_provider_mode"] = provider_mode
        return {
            "product_id_str": product_id_str,
            "product_info": product_info,
            "reference_image_urls": reference_image_urls,
            "reference_product_images": selected["reference_product_images"],
            "reference_scene_images": selected["reference_scene_images"],
            "image_provider_id": task_cfg.image_provider_id if task_cfg else None,
            "image_provider_mode": provider_mode,
            "image_model": task_cfg.image_model if task_cfg else None,
            "image_size": getattr(task_cfg, "image_size", None) if task_cfg else None,
            "owner_user_id": owner_user_id,
        }

    def execute_auto_task(self, task_id, target_categories, target_products, platforms,
                          reference_image_count, run_count_per_execution, use_scene_reference=False):
        logger.info(f"Executing auto task {task_id} at {datetime.now()}")

        session = Session(bind=engine)
        try:
            task = session.query(ScheduledTask).filter(ScheduledTask.task_id == task_id).first()
            if not task:
                logger.error("Scheduled task not found: %s", task_id)
                return
            products = products_for_task(session, task)
            product_ids = [str(p.product_id) for p in products]
            task_owner = _task_owner(task)
        finally:
            session.close()

        if not product_ids:
            logger.error("No product found in target categories or products")
            return

        # run_count = 完整轮次；每轮按勾选顺序为每个产品各生成一次
        for round_idx in range(run_count_per_execution):
            for product_id in product_ids:
                execution_id = str(uuid.uuid4())
                session = Session(bind=engine)
                try:
                    execution = TaskExecution(
                        execution_id=execution_id,
                        task_id=task_id,
                        product_id=str(product_id),
                        status="RUNNING"
                    )
                    stamp_owner(execution, task_owner)
                    session.add(execution)
                    session.commit()
                finally:
                    session.close()

                result = None
                error_message = None
                try:
                    result = self._execute_single_run(
                        task_id, product_id, platforms,
                        reference_image_count, use_scene_reference,
                    )
                except Exception as e:
                    error_message = str(e)
                    logger.error(
                        "Error executing task workflow (round %s, product %s): %s",
                        round_idx + 1,
                        product_id,
                        e,
                        exc_info=True,
                    )

                session = Session(bind=engine)
                try:
                    execution = session.query(TaskExecution).filter(
                        TaskExecution.execution_id == execution_id
                    ).first()
                    if not execution:
                        continue
                    if result is not None:
                        execution.status = "SUCCESS"
                        execution.generated_images = result.get("images", [])
                        execution.published_platforms = result.get("platforms", [])
                        execution.copywriting = result.get("copywriting", "")
                        execution.dimensions = result.get("dimensions")
                        execution.image_prompt = result.get("image_prompt")
                        execution.reference_product_images = result.get("reference_product_images", [])
                        execution.reference_scene_images = result.get("reference_scene_images", [])
                    else:
                        execution.status = "FAILED"
                        execution.error_message = error_message
                    session.commit()
                finally:
                    session.close()

        session = Session(bind=engine)
        try:
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

        contexts = []
        session = Session(bind=engine)
        try:
            task = session.query(ScheduledTask).filter(ScheduledTask.task_id == task_id).first()
            if not task:
                logger.error("Scheduled task not found: %s", task_id)
                return
            products = products_for_task(session, task)
            if not products:
                logger.error("No product found in target categories or products")
                return
            for product in products:
                contexts.append(
                    self._prepare_product_context(
                        session,
                        product,
                        task_id,
                        reference_image_count,
                        use_scene_reference,
                        platforms,
                    )
                )
        except Exception as e:
            logger.error(f"Error preparing manual task {task_id}: {str(e)}", exc_info=True)
            return
        finally:
            session.close()

        platform = platforms[0] if platforms else "instagram"
        saved_any = False

        for ctx in contexts:
            product_id_str = ctx["product_id_str"]
            product_info = ctx["product_info"]
            try:
                copywritings = []
                for i in range(generate_copy_count):
                    copywriting = content_generator.generate_copywriting(product_info, platform)
                    copywritings.append(copywriting)
                    logger.info(
                        "Generated copywriting %s/%s for product %s: %s...",
                        i + 1,
                        generate_copy_count,
                        product_id_str,
                        copywriting[:100],
                    )

                images = []
                dimensions_list = []
                image_prompts_list = []
                for i in range(generate_image_count):
                    # 本批次已生成的 prompt 尚未入库，一并作为避让上下文
                    product_info["avoid_image_prompts"] = [
                        p for p in image_prompts_list if p
                    ]
                    image_result = _run_platform_image_generation(
                        ctx["owner_user_id"],
                        ctx.get("image_provider_mode"),
                        lambda: content_generator.generate_image(
                            product_info,
                            platform,
                            ctx["reference_image_urls"],
                            image_provider_id=ctx["image_provider_id"],
                            image_model=ctx["image_model"],
                            image_size=ctx.get("image_size"),
                        ),
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
                    logger.info(
                        "Generated image %s/%s for product %s: %s",
                        i + 1,
                        generate_image_count,
                        product_id_str,
                        image_urls[0],
                    )

                if not copywritings or not images:
                    raise Exception("Manual task produced empty copywritings or images; draft not saved")

                session = Session(bind=engine)
                try:
                    draft = ManualTaskDraft(
                        draft_id=str(uuid.uuid4()),
                        task_id=task_id,
                        product_id=product_id_str,
                        images=images,
                        copywritings=copywritings,
                        dimensions=dimensions_list,
                        image_prompts=image_prompts_list,
                        reference_product_images=ctx["reference_product_images"],
                        reference_scene_images=ctx["reference_scene_images"],
                        status="pending"
                    )
                    stamp_owner(draft, SimpleNamespace(user_id=ctx["owner_user_id"]))
                    session.add(draft)
                    session.commit()
                    saved_any = True
                    logger.info(
                        "Manual task %s draft saved for product %s (%s images, %s copywritings)",
                        task_id,
                        product_id_str,
                        len(images),
                        len(copywritings),
                    )
                finally:
                    session.close()
            except Exception as e:
                logger.error(
                    "Error generating for product %s in manual task %s: %s — continuing with remaining products",
                    product_id_str,
                    task_id,
                    e,
                    exc_info=True,
                )

        if not saved_any:
            logger.error("Manual task %s produced no drafts", task_id)
            return

        session = Session(bind=engine)
        try:
            task = session.query(ScheduledTask).filter(ScheduledTask.task_id == task_id).first()
            if task:
                task.last_run_at = datetime.now()
                if str(task_id) in self.running_tasks:
                    job = self.running_tasks[str(task_id)]
                    task.next_run_at = job.next_run_time
                session.commit()
        finally:
            session.close()
    
    def _execute_single_run(self, task_id, product_id, platforms,
                            reference_image_count, use_scene_reference=False):
        session = Session(bind=engine)
        try:
            product = session.query(Product).filter(Product.product_id == product_id).first()
            if not product:
                logger.error("Product not found: %s", product_id)
                return {"images": [], "platforms": [], "copywriting": ""}
            ctx = self._prepare_product_context(
                session, product, task_id, reference_image_count, use_scene_reference, platforms
            )
            try:
                api_token = resolve_buffer_api_token(
                    session,
                    product_id=product_id,
                    owner_user_id=ctx["owner_user_id"],
                )
            except BufferAccountUnavailable as exc:
                raise Exception(exc.message) from exc
        finally:
            session.close()

        if not api_token:
            raise Exception(
                "未绑定 Buffer 账户。请到「品牌管理」为该品牌绑定 Buffer 账户后再发布。"
            )

        product_info = ctx["product_info"]
        reference_image_urls = ctx["reference_image_urls"]
        reference_product_images = ctx["reference_product_images"]
        reference_scene_images = ctx["reference_scene_images"]
        platform = platforms[0] if platforms else "instagram"

        copywriting = content_generator.generate_copywriting(product_info, platform)
        logger.info(f"Generated copywriting: {copywriting[:100]}...")

        image_result = _run_platform_image_generation(
            ctx["owner_user_id"],
            ctx.get("image_provider_mode"),
            lambda: content_generator.generate_image(
                product_info,
                platform,
                reference_image_urls,
                image_provider_id=ctx["image_provider_id"],
                image_model=ctx["image_model"],
                image_size=ctx.get("image_size"),
            ),
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

        publish_result = buffer_publisher.publish(
            copywriting, cdn_url, platforms, api_token=api_token
        )
        logger.info(f"Publish result: {publish_result}")

        success_platforms = []
        for platform_name, result in publish_result.items():
            if result.get("success"):
                success_platforms.append(platform_name)
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
