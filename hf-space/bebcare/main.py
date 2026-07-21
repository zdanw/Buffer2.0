from fastapi import FastAPI, Depends, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from bebcare.api import product_router, task_router, generate_router, publish_router, auth_router, prompt_dimension_router
from bebcare.database import init_db
from bebcare.config.settings import settings
from bebcare.scheduler.apscheduler_service import scheduler_service
from bebcare.services.auth_dependency import get_current_active_user
from bebcare.initial_data import initialize_data
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

init_db()

app = FastAPI(
    title="Bebcare AI Studio API",
    description="全自动社媒内容生成与发布系统",
    version="2.0.0"
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    # 不记录 Authorization 等敏感头
    logger.info("Request: %s %s", request.method, request.url.path)
    response = await call_next(request)
    logger.info("Response: %s %s -> %s", request.method, request.url.path, response.status_code)
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

app.include_router(api_router)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting Bebcare AI Studio API (env=%s)", settings.app_env)
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