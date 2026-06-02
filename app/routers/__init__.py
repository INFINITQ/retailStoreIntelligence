from app.routers.events import router as events_router
from app.routers.health import router as health_router
from app.routers.stores import router as stores_router

__all__ = ["events_router", "stores_router", "health_router"]
