"""FastAPI application entrypoint."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.bootstrap import bootstrap_admin
from app.api.routers.auth import router as auth_router
from app.api.routers.health import router as health_router
from app.api.routers.uploads import router as uploads_router
from app.api.routers.presentations import router as presentations_router
from app.api.routers.jobs import router as jobs_router
from app.api.routers.search import router as search_router
from app.api.routers.tags import router as tags_router
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(health_router, tags=["health"])
    app.include_router(auth_router)
    app.include_router(uploads_router)
    app.include_router(presentations_router)
    app.include_router(jobs_router)
    app.include_router(search_router)
    app.include_router(tags_router)

    @app.on_event("startup")
    def _startup() -> None:
        try:
            bootstrap_admin()
        except Exception as e:  # noqa: BLE001
            logger.warning("bootstrap_admin failed (DB may not be ready yet): %s", e)

    @app.get("/")
    def root() -> dict:
        return {"app": settings.APP_NAME, "version": settings.APP_VERSION, "status": "running"}

    return app


app = create_app()
