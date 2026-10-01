"""FastAPI entry point. Domain routers are added by later tasks (docs/tasks/BACKLOG.md)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from cavat import __version__, db
from cavat.modules.session import api as session_api


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await db.close_client()


app = FastAPI(title="CAVAT API", version=__version__, lifespan=lifespan)
session_api.register(app)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/health/db")
async def health_db():
    try:
        await db.ping()
    except db.DatabaseNotConfiguredError:
        return JSONResponse(status_code=503, content={"status": "not_configured"})
    except Exception as exc:  # network or auth failure
        return JSONResponse(status_code=503, content={"status": "unreachable", "error": type(exc).__name__})
    return {"status": "ok"}
