from __future__ import annotations

from contextlib import asynccontextmanager
from threading import Event

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from api import accounts, ai, gemini, image_tasks, system
from api.errors import install_exception_handlers
from api.support import resolve_web_asset, start_limited_account_watcher
from services.backup_service import backup_service
from services.config import config


class _PathNormalizeMiddleware:
    """Normalize request paths before routing.

    Some OpenAI-compatible clients build slightly different URLs:
    - duplicate slashes: //v1/chat/completions -> /v1/chat/completions
    - trailing slash: /v1/chat/completions/ -> /v1/chat/completions
    - DeepSeek-style (no /v1): /chat/completions -> /v1/chat/completions,
      /models -> /v1/models

    Without this, such requests fall through to the SPA catch-all route,
    which only accepts GET and answers POST with 405.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            path = scope.get("path", "")
            while "//" in path:
                path = path.replace("//", "/")
            if len(path) > 1 and path.endswith("/"):
                path = path.rstrip("/")
            if path == "/chat/completions":
                path = "/v1/chat/completions"
            elif path == "/models":
                path = "/v1/models"
            scope["path"] = path
        await self.app(scope, receive, send)


def create_app() -> FastAPI:
    app_version = config.app_version

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        stop_event = Event()
        thread = start_limited_account_watcher(stop_event)
        backup_service.start()
        config.cleanup_old_images()
        try:
            yield
        finally:
            stop_event.set()
            thread.join(timeout=1)
            backup_service.stop()

    app = FastAPI(title="webchat2api", version=app_version, lifespan=lifespan)
    install_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(_PathNormalizeMiddleware)
    app.include_router(ai.create_router())
    app.include_router(gemini.create_router())
    app.include_router(accounts.create_router())
    app.include_router(image_tasks.create_router())
    app.include_router(system.create_router(app_version))

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_web(full_path: str):
        asset = resolve_web_asset(full_path)
        if asset is not None:
            return FileResponse(asset)
        if full_path.strip("/").startswith("_next/"):
            raise HTTPException(status_code=404, detail="Not Found")
        fallback = resolve_web_asset("")
        if fallback is None:
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(fallback)

    return app
