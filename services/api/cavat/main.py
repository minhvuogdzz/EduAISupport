"""FastAPI entry point. Domain routers are added by later tasks (docs/tasks/BACKLOG.md).

REL-1 (ADR-035): one port. ``create_app`` also serves the web app of apps/web/dist (``cavat.webapp``),
compresses what it sends, adds the light security headers and keeps /docs off unless ``API_DOCS=1``. There is
no CORS: the web app and the API share one origin, so a page of another site cannot read an answer.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.gzip import GZipMiddleware

from cavat import __version__, db, webapp
from cavat.config import get_settings
from cavat.modules.session import api as session_api


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await db.close_client()


def create_app(*, web_dist: Path | None = None, api_docs: bool | None = None) -> FastAPI:
    """The API; ``web_dist`` and ``api_docs`` default to WEB_DIST and API_DOCS of the settings."""
    settings = get_settings()
    dist = settings.web_dist if web_dist is None else web_dist
    docs = settings.api_docs if api_docs is None else api_docs
    app = FastAPI(
        title="CAVAT API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )
    session_api.register(app)

    @app.get("/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "version": __version__,
            "revision": os.environ.get("CAVAT_REVISION", "development"),
        }

    @app.get("/health/db")
    async def health_db():
        try:
            await db.ping()
        except db.DatabaseNotConfiguredError:
            return JSONResponse(status_code=503, content={"status": "not_configured"})
        except Exception as exc:  # network or auth failure
            return JSONResponse(
                status_code=503, content={"status": "unreachable", "error": type(exc).__name__}
            )
        return {"status": "ok"}

    webapp.install(app, dist)
    app.add_middleware(GZipMiddleware, minimum_size=1024)  # audio and event streams are left alone
    app.add_middleware(webapp.SecurityHeaders)  # added last, so outermost: it also covers the 304 and the 404
    return app


app = create_app()
