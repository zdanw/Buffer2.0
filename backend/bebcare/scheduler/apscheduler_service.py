from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.executors.pool import ThreadPoolExecutor
from datetime import datetime
from types import SimpleNamespace
from bebcare.generator.content_generator import content_generator
from bebcare.dedup.deduplication_engine import deduplication_engine
from bebcare.publisher.buffer_publisher import buffer_publisher
from bebcare.models import ScheduledTask, TaskExecution, ManualTaskDraft, Product
from bebcare.models.user import User
from bebcare.utils.reference_selector import resolve_generate_references
from bebcare.services.brand_context import enrich_product_info
from bebcare.services.buffer_account_service import (
    resolve_buffer_api_token,
    BufferAccountUnavailable,
)
from bebcare.services.ownership import stamp_owner
from bebcare.config.settings import settings
from bebcare.services.grounded_rollout import grounded_rollout_mode, selection_provenance
from bebcare.services.generate_task_store import (
    create_generate_task,
    update_generate_task,
)
from bebcare.services.credit_grant_service import CreditError, reserve_one
from bebcare.utils.user_errors import SCHEDULER_IMAGE_FAILED, user_safe_task_error
from bebcare.services.email_service import send_auto_publish_notification
from sqlalchemy.orm import Session
from bebcare.database import engine
import logging
import threading
import uuid

logger = logging.getLogger(__name__)


def _run_expire_due_grants():
    from bebcare.database import SessionLocal
    from bebcare.services.credit_grant_service import expire_due_grants

    db = SessionLocal()
    try:
        n = expire_due_grants(db)
        db.commit()
        if n:
            logger.info("Expired %s image credit grant(s)", n)
    except Exception:
        db.rollback()
        logger.exception("expire_due_grants failed")
    finally:
        db.close()


def _run_platform_image_generation(
    owner_user_id: str,
    mode: str | None,
    generate_fn,
    *,
    ctx: dict | None = None,
    scheduled_task_id: str | None = None,
):
    """Reserve one platform credit around a single image generation when mode=platform."""
    from bebcare.models.generation_run import GenerationRun
    from bebcare.services.generation_run_store import (
        build_output_snapshot,
        create_generation_run,
        finish_generation_run,
    )
    from bebcare.services.quality_protection_rollout import (
        POLICY_VERSION,
        quality_protection_mode,
    )
    from bebcare.services.product_fidelity_rollout import (
        VISUAL_POLICY_VERSION,
        product_fidelity_prevention_mode,
        visual_fidelity_qa_mode,
    )
    from bebcare.services.grounded_rollout import SOURCE_AUTOMATION, grounded_rollout_mode

    gen_task_id = None
    if mode == "platform":
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
                result={"error": user_safe_task_error(exc)},
            )
            raise Exception(
                "平台出图额度不足，调度任务无法使用平台供应商出图（不会静默切换到 BYOK）"
            ) from exc
        finally:
            session.close()

    run_id = None
    if ctx is not None:
        provenance = (ctx.get("product_info") or {}).get("generation_provenance") or {}
        session = Session(bind=engine)
        try:
            run = create_generation_run(
                session,
                owner_user_id=owner_user_id,
                source=SOURCE_AUTOMATION,
                product_id=ctx.get("product_id_str"),
                generate_task_id=gen_task_id,
                scheduled_task_id=scheduled_task_id,
                rollout_mode_at_start=provenance.get("rollout_mode_at_start")
                or grounded_rollout_mode(),
                experiment_variant=provenance.get("experiment_variant"),
                requested_pipeline_version=provenance.get("requested_pipeline_version")
                or "baseline_current",
                executed_pipeline_version=provenance.get("executed_pipeline_version")
                or "legacy_random_refs",
                fallback_reason=provenance.get("fallback_reason"),
                fallback_path=provenance.get("fallback_path"),
                image_prompt_pipeline=None,
                compare_group_id=None,
                generation_plan=ctx.get("product_info", {}).get("generation_plan")
                or provenance.get("generation_plan"),
                reference_manifest=provenance.get("reference_manifest"),
                provider_id=ctx.get("image_provider_id"),
                model=ctx.get("image_model"),
                image_size=ctx.get("image_size"),
                image_provider_mode=mode,
                quality_protection_mode=quality_protection_mode(),
                quality_policy_version=POLICY_VERSION,
                product_fidelity_prevention_mode=product_fidelity_prevention_mode(),
                visual_fidelity_qa_mode=visual_fidelity_qa_mode(),
                visual_fidelity_policy_version=VISUAL_POLICY_VERSION,
                requested_selector_strategy=provenance.get("requested_selector_strategy"),
                executed_selector_strategy=provenance.get("executed_selector_strategy"),
                selection_seed=provenance.get("selection_seed"),
            )
            session.commit()
            run_id = run.run_id
            if ctx.get("product_info") is not None:
                ctx["product_info"]["generation_run_id"] = run_id
                from bebcare.services.quality_diversity_events import attach_from_product_info

                attach_from_product_info(
                    session,
                    run,
                    ctx.get("product_info"),
                    source=SOURCE_AUTOMATION,
                    task_mode=ctx.get("task_mode"),
                )
                session.commit()
                ctx["product_info"]["owner_user_id"] = owner_user_id
        finally:
            session.close()

    try:
        result = generate_fn()
        image_urls = result.get("image_urls") if isinstance(result, dict) else result
        warning = result.get("warning") if isinstance(result, dict) else None
        if gen_task_id:
            first = image_urls[0] if image_urls else None
            update_generate_task(
                gen_task_id,
                status="SUCCESS",
                set_result=True,
                result={"image": first, "warning": warning} if first else None,
            )
        if run_id:
            session = Session(bind=engine)
            try:
                run = session.query(GenerationRun).filter(GenerationRun.run_id == run_id).first()
                if run:
                    finish_generation_run(
                        session,
                        run,
                        status="succeeded",
                        image_urls=list(image_urls or []),
                        persistence_warning=warning,
                        output_snapshot=build_output_snapshot(result) if isinstance(result, dict) else None,
                    )
                    session.commit()
            finally:
                session.close()
        return result
    except Exception:
        if gen_task_id:
            update_generate_task(
                gen_task_id,
                status="FAILURE",
                set_result=True,
                result={"error": SCHEDULER_IMAGE_FAILED},
            )
        elif run_id:
            session = Session(bind=engine)
            try:
                run = session.query(GenerationRun).filter(GenerationRun.run_id == run_id).first()
                if run:
                    finish_generation_run(
                        session, run, status="failed", error_category="scheduler_image_failed"
                    )
                    session.commit()
            finally:
                session.close()
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


def _maybe_send_publish_notification(session, task, product_id: str, result: dict):
    if not task or not getattr(task, "notify_on_publish", False):
        return
    if task.mode != "auto":
        return
    if not result.get("platforms"):
        return

    user = session.query(User).filter(User.user_id == task.owner_user_id).first()
    if not user or not user.email:
        logger.warning(
            "Auto-publish email skipped for task %s: owner has no email",
            task.task_id,
        )
        return

    product_name = result.get("product_name") or product_id
    platform_posts = result.get("platform_posts") or []
    image_url = (result.get("images") or [None])[0]

    send_auto_publish_notification(
        user.email,
        task_name=task.name,
        product_name=product_name,
        copywriting=result.get("copywriting") or "",
        image_url=image_url,
        platform_posts=platform_posts,
    )


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
        minutes = max(1, int(settings.image_credit_expire_interval_minutes))
        self.scheduler.add_job(
            _run_expire_due_grants,
            trigger=IntervalTrigger(minutes=minutes),
            id="expire_image_credit_grants",
            replace_existing=True,
            max_instances=1,
        )
        logger.info(
            "APScheduler started (workers=%s, max_concurrent_jobs=%s, max_instances=%s, credit_expire_every=%sm)",
            settings.scheduler_max_workers,
            settings.max_concurrent_jobs,
            settings.scheduler_max_instances,
            minutes,
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
        task_cfg = session.query(ScheduledTask).filter(ScheduledTask.task_id == task_id).first()
        from bebcare.services.asset_intelligence import load_usable_analyses
        from bebcare.services.quality_diversity_context import build_selector_context

        intel = {}
        try:
            intel = load_usable_analyses(
                session,
                owner_user_id=product.owner_user_id,
                product_id=str(product.product_id),
            )
        except Exception:
            intel = {}
        brand = getattr(product, "brand", None)
        selector_ctx = build_selector_context(
            source="automation",
            product=product,
            task_mode=getattr(task_cfg, "mode", None) if task_cfg else None,
            image_size=getattr(task_cfg, "image_size", None) if task_cfg else None,
            use_scene_reference=use_scene_reference,
            realistic_placement=bool(getattr(task_cfg, "realistic_placement", True)) if task_cfg else True,
            reference_count=reference_image_count,
            logo_mode=getattr(brand, "logo_in_images", None) if brand is not None else None,
            intelligence_by_image=intel,
        )
        selected = resolve_generate_references(
            session,
            product_id=product.product_id,
            owner_user_id=product.owner_user_id,
            reference_count=reference_image_count,
            use_scene_reference=use_scene_reference,
            source="automation",
            task_mode=getattr(task_cfg, "mode", None) if task_cfg else None,
            image_size=getattr(task_cfg, "image_size", None) if task_cfg else None,
            selector_context=selector_ctx,
        )
        reference_image_urls = selected.reference_images
        effective_scene = selected.use_scene_reference
        logger.info(
            "Product %s reference images (%s): %s",
            product.product_id,
            len(reference_image_urls),
            reference_image_urls,
        )
        logger.info("Scene reference mode: %s", effective_scene)

        product_id_str = str(product.product_id)
        base_info = {
            "product_id": product_id_str,
            "product_name": product.product_name,
            "category": product.category,
            "description": product.description,
            "selling_points": product.selling_points,
            "brand_voice": product.brand_voice,
            "reference_images": reference_image_urls,
            "reference_product_images": selected.reference_product_images,
            "reference_scene_images": selected.reference_scene_images,
            "platform": platforms[0] if platforms else "instagram",
            "use_scene_reference": effective_scene,
            "use_vision_image_prompt": bool(
                getattr(task_cfg, "use_vision_image_prompt", False)
            )
            if task_cfg
            else False,
            "realistic_placement": bool(
                getattr(task_cfg, "realistic_placement", True)
            )
            if task_cfg
            else True,
            "experiment_variant": selected.experiment_variant,
            "executed_pipeline_version": selected.executed_pipeline_version,
            "grounded_phase1b_enabled": bool(selected.grounded),
            "generation_provenance": selection_provenance(
                selected, source="automation"
            ),
        }
        product_info = enrich_product_info(session, product, base_info)
        from bebcare.services.generation_plan import attach_generation_plan

        attach_generation_plan(product_info)
        owner_user_id = (
            task_cfg.owner_user_id if task_cfg else product.owner_user_id
        )
        provider_mode = (
            getattr(task_cfg, "image_provider_mode", None) if task_cfg else None
        ) or "byok"
        product_info["owner_user_id"] = owner_user_id
        product_info["image_provider_mode"] = provider_mode
        product_info["task_mode"] = getattr(task_cfg, "mode", None) if task_cfg else None
        return {
            "product_id_str": product_id_str,
            "product_info": product_info,
            "reference_image_urls": reference_image_urls,
            "reference_product_images": selected.reference_product_images,
            "reference_scene_images": selected.reference_scene_images,
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
                        execution.platform_posts = result.get("platform_posts", [])
                        execution.copywriting = result.get("copywriting", "")
                        execution.dimensions = result.get("dimensions")
                        execution.image_prompt = result.get("image_prompt")
                        execution.reference_product_images = result.get("reference_product_images", [])
                        execution.reference_scene_images = result.get("reference_scene_images", [])
                        task = session.query(ScheduledTask).filter(
                            ScheduledTask.task_id == task_id
                        ).first()
                        _maybe_send_publish_notification(session, task, str(product_id), result)
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
                        ctx=ctx,
                        scheduled_task_id=task_id,
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
            ctx=ctx,
            scheduled_task_id=task_id,
        )
        image_urls = image_result.get("image_urls") if isinstance(image_result, dict) else image_result
        dimensions = image_result.get("dimensions") if isinstance(image_result, dict) else None
        image_prompt = image_result.get("image_prompt") if isinstance(image_result, dict) else None
        if not image_urls:
            raise Exception("Auto task image generation returned no URLs; publish aborted")
        logger.info(f"Generated images: {image_urls}")

        from bebcare.services.grounded_rollout import SOURCE_AUTOMATION
        from bebcare.services.quality_protection import apply_publish_gate

        gate_session = Session(bind=engine)
        try:
            gate = apply_publish_gate(
                gate_session,
                owner_user_id=ctx["owner_user_id"],
                run_id=(ctx.get("product_info") or {}).get("generation_run_id"),
                source=SOURCE_AUTOMATION,
                task_mode="auto",
                hard_fail=bool(isinstance(image_result, dict) and image_result.get("quality_hard_fail")),
                image_urls=list(image_urls),
            )
            gate_session.commit()
        finally:
            gate_session.close()
        if gate.get("blocked"):
            draft_session = Session(bind=engine)
            try:
                draft = ManualTaskDraft(
                    draft_id=str(uuid.uuid4()),
                    task_id=task_id,
                    product_id=str(product_id),
                    images=list(image_urls),
                    copywritings=[copywriting],
                    dimensions=[dimensions],
                    image_prompts=[image_prompt],
                    reference_product_images=reference_product_images,
                    reference_scene_images=reference_scene_images,
                    status="pending",
                )
                stamp_owner(draft, SimpleNamespace(user_id=ctx["owner_user_id"]))
                draft_session.add(draft)
                draft_session.commit()
            finally:
                draft_session.close()
            logger.info(
                "Auto task %s publish paused; draft routed to Review product=%s",
                task_id,
                product_id,
            )
            return {
                "images": list(image_urls),
                "platforms": [],
                "copywriting": copywriting,
                "dimensions": dimensions,
                "image_prompt": image_prompt,
                "reference_product_images": reference_product_images,
                "reference_scene_images": reference_scene_images,
                "warning": gate.get("warning"),
                "publish_paused": True,
            }

        generated_images = []
        published_platforms = []

        publish_url = gate.get("selected_url") or image_urls[0]
        similarity = deduplication_engine.calculate_text_image_match(copywriting, publish_url)
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
        cdn_url = publish_url
        generated_images.append(cdn_url)

        publish_result = buffer_publisher.publish(
            copywriting, cdn_url, platforms, api_token=api_token
        )
        logger.info(f"Publish result: {publish_result}")

        success_platforms = []
        platform_posts = []
        for platform_name, pub in publish_result.items():
            if pub.get("success"):
                success_platforms.append(platform_name)
                platform_posts.append({
                    "platform": platform_name,
                    "channel": pub.get("channel"),
                    "post_id": pub.get("post_id"),
                    "post_link": pub.get("post_link") or pub.get("external_link"),
                })
        published_platforms = success_platforms

        if not published_platforms:
            raise Exception(f"Buffer publish failed for all platforms: {publish_result}")

        return {
            "images": generated_images,
            "platforms": published_platforms,
            "platform_posts": platform_posts,
            "product_name": product_info.get("product_name") or str(product_id),
            "copywriting": copywriting,
            "dimensions": dimensions,
            "image_prompt": image_prompt,
            "reference_product_images": reference_product_images,
            "reference_scene_images": reference_scene_images,
        }

scheduler_service = APSchedulerService()
