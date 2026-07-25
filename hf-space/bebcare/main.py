from fastapi import FastAPI, Depends, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from bebcare.api.product_routes import router as product_router
from bebcare.api.task_routes import router as task_router
from bebcare.api.generate_routes import router as generate_router
from bebcare.api.publish_routes import router as publish_router
from bebcare.api.auth_routes import router as auth_router
from bebcare.api.prompt_dimension_routes import router as prompt_dimension_router
from bebcare.api.image_provider_routes import router as image_provider_router
from bebcare.database import init_db
from bebcare.config.settings import settings
from bebcare.logging_config import setup_logging
from bebcare.scheduler.apscheduler_service import scheduler_service
from bebcare.services.auth_dependency import get_current_active_user
from bebcare.initial_data import initialize_data
import logging
import time

setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

init_db()

app = FastAPI(
    title="Bebcare AI Studio API",
    description="全自动社媒内容生成与发布系统",
    version="2.0.0"
)

# 探活、文档与高频轮询不刷请求日志，避免 HF Logs 被淹没
_SKIP_REQUEST_LOG_PATHS = frozenset({"/", "/health", "/docs", "/openapi.json", "/redoc"})
_SKIP_REQUEST_LOG_PREFIXES = ("/v1/generate/status/",)


def _should_skip_request_log(path: str) -> bool:
    if path in _SKIP_REQUEST_LOG_PATHS:
        return True
    if any(path.startswith(prefix) for prefix in _SKIP_REQUEST_LOG_PREFIXES):
        return True
    # 只记录业务 API；/.env、/graphql、/actuator 等公网扫描一律忽略
    if not path.startswith("/v1/"):
        return True
    return False


@app.middleware("http")
async def log_requests(request: Request, call_next):
    path = request.url.path
    skip = _should_skip_request_log(path)
    started = time.perf_counter()
    if not skip:
        logger.info("→ %s %s", request.method, path)
    response = await call_next(request)
    if not skip:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "← %s %s -> %s (%.0fms)",
            request.method,
            path,
            response.status_code,
            elapsed_ms,
        )
    return response

cors_origins = settings.cors_origins
if not cors_origins:
    raise RuntimeError(
        "ALLOWED_ORIGINS 为空或仅包含 *。请配置显式前端域名白名单，例如 "
        "http://localhost:5173,https://your-app.vercel.app"
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/v1")
api_router.include_router(auth_router)
api_router.include_router(product_router, dependencies=[Depends(get_current_active_user)])
api_router.include_router(task_router, dependencies=[Depends(get_current_active_user)])
api_router.include_router(generate_router, dependencies=[Depends(get_current_active_user)])
api_router.include_router(publish_router, dependencies=[Depends(get_current_active_user)])
api_router.include_router(prompt_dimension_router, dependencies=[Depends(get_current_active_user)])
api_router.include_router(image_provider_router)

app.include_router(api_router)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting Bebcare AI Studio API (env=%s, log_level=%s)", settings.app_env, settings.log_level)
    logger.info("CORS allow_origins=%s", cors_origins)
    initialize_data()
    scheduler_service.start()
    scheduler_service.reload_enabled_tasks()

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Bebcare AI Studio API")
    scheduler_service.stop()

@app.get("/")
async def root():
    return {"message": "Welcome to Bebcare AI Studio API"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.app_host, port=settings.app_port)
