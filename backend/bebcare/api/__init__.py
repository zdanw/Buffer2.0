from .product_routes import router as product_router
from .task_routes import router as task_router
from .generate_routes import router as generate_router
from .publish_routes import router as publish_router
from .auth_routes import router as auth_router

__all__ = ["product_router", "task_router", "generate_router", "publish_router", "auth_router"]