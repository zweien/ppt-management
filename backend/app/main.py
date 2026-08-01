"""FastAPI application entrypoint."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.bootstrap import bootstrap_admin, bootstrap_default_embedding
from app.api.routers.auth import router as auth_router
from app.api.routers.health import router as health_router
from app.api.routers.uploads import router as uploads_router
from app.api.routers.presentations import router as presentations_router
from app.api.routers.jobs import router as jobs_router
from app.api.routers.search import router as search_router
from app.api.routers.tags import router as tags_router
from app.api.routers.folders import router as folders_router
from app.api.routers.duplicates import router as duplicates_router
from app.api.routers.api_keys import router as api_keys_router
from app.api.routers.compose import router as compose_router
from app.api.routers.model_configs import router as model_configs_router
from app.api.routers.settings import router as settings_router
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
    app.include_router(folders_router)
    app.include_router(duplicates_router)
    app.include_router(api_keys_router)
    app.include_router(compose_router)
    app.include_router(model_configs_router)
    app.include_router(settings_router)

    @app.on_event("startup")
    def _startup() -> None:
        try:
            bootstrap_admin()
            bootstrap_default_embedding()
        except Exception as e:  # noqa: BLE001
            logger.warning("bootstrap failed (DB may not be ready yet): %s", e)

    @app.get("/")
    def root() -> dict:
        from app.services.runtime_config import (
            get_app_name,
            get_default_theme,
            get_mesh_enabled,
            get_logo_object_key,
            get_upload_extensions,
            get_upload_max_size_mb,
        )
        return {
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "running",
            "upload_limits": {
                "max_size_mb": get_upload_max_size_mb(),
                "allowed_extensions": get_upload_extensions(),
            },
            "ui_config": {
                "app_name": get_app_name(),
                "logo_url": "/api/settings/logo" if get_logo_object_key() else None,
                "mesh_enabled": get_mesh_enabled(),
                "default_theme": get_default_theme(),
            },
        }

    return app


app = create_app()
