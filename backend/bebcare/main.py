from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from bebcare.api import product_router, task_router, generate_router, publish_router
from bebcare.database import engine, Base
from bebcare.config.settings import settings
from bebcare.scheduler.apscheduler_service import scheduler_service
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Bebcare AI Studio API",
    description="全自动社媒内容生成与发布系统",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(product_router)
app.include_router(task_router)
app.include_router(generate_router)
app.include_router(publish_router)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting Bebcare AI Studio API")
    scheduler_service.start()

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