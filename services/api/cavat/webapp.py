"""One port (REL-1, ADR-034): the API serves the web app it belongs to.

``make run`` builds apps/web (``VITE_API=http``) and starts the API alone; the browser, and through the
Cloudflare tunnel every student's browser, talks to that one address. Routes win: whatever the API answers is
the API's. What no route answers goes through the 404 handler below:

- a path of the API (``/v1/...``, ``/health...``, the docs paths) stays a JSON 404 in the API's error format,
  never ``index.html``, so a client that calls a wrong path reads an error and not a web page;
- a file of the build is served as it is: ``assets/*`` carry a hash in their name, so they are cached for a
  year; everything else is revalidated (ETag), ``index.html`` above all, or a new build reaches no one;
- any other path without a file extension is a path of the web app (``/student/...``, ``/teacher/...``): the
  app's ``index.html``, and its router reads the address;
- a missing file (``/assets/gone.js``, ``/favicon.ico``) is a 404, not a web page the browser cannot run.

No build in the folder: the API alone, as before (``make web-live`` talks to it through the Vite dev server).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Paths that belong to the API even when no route answers them (a typo, a removed endpoint, the docs).
API_PATHS = ("/v1", "/health", "/docs", "/redoc", "/openapi.json")

IMMUTABLE = "public, max-age=31536000, immutable"  # a file whose name holds its hash never changes
REVALIDATE = "no-cache"  # keep a copy, ask the server before every use (304 when unchanged)


def is_api_path(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in API_PATHS)


def not_found() -> JSONResponse:
    body = {"error": {"code": "NOT_FOUND", "message": "not found", "details": {}}}
    return JSONResponse(status_code=404, content=body)


class WebApp:
    """The files of a vite build, served by path."""

    def __init__(self, dist: Path) -> None:
        self.dist = dist
        self.available = (dist / "index.html").is_file()
        self._files = StaticFiles(directory=dist) if self.available else None

    async def respond(self, request: Request) -> Response | None:
        """The file or the app page for a GET of ``request``; None when it is neither (a 404)."""
        if self._files is None or request.method not in ("GET", "HEAD") or is_api_path(request.url.path):
            return None
        path = request.url.path.strip("/")
        if any(part.startswith(".") for part in path.split("/")):
            return None  # .cavat-build and the like are not for the browser
        scope = request.scope
        try:
            response = await self._files.get_response(path or "index.html", scope)
        except HTTPException as exc:
            name = path.rsplit("/", 1)[-1]
            if exc.status_code != 404 or "." in name or (path + "/").startswith("assets/"):
                return None  # a file that is not there, or a lazy chunk the build no longer has
            try:
                response = await self._files.get_response("index.html", scope)
            except HTTPException:
                return None
            path = "index.html"
        hashed = path.startswith("assets/") and response.status_code == 200
        response.headers["Cache-Control"] = IMMUTABLE if hashed else REVALIDATE
        return response


class SecurityHeaders:
    """Light headers on every response: no MIME sniffing, no referrer to other sites, no framing."""

    HEADERS = (
        (b"x-content-type-options", b"nosniff"),
        (b"referrer-policy", b"same-origin"),
        (b"x-frame-options", b"DENY"),
        (b"content-security-policy", b"frame-ancestors 'none'"),
    )

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                present = {name.lower() for name, _ in message["headers"]}
                message["headers"] = [*message["headers"], *(h for h in self.HEADERS if h[0] not in present)]
            await send(message)

        await self.app(scope, receive, with_headers)


def install(app: FastAPI, dist: Path) -> WebApp:
    """Route the paths no route answers: the web app's files and pages, and the API's JSON 404."""
    web = WebApp(dist)

    async def handle_http(request: Request, exc: HTTPException) -> Response:
        if exc.status_code != 404:
            return await http_exception_handler(request, exc)  # 405 and the rest: FastAPI's own answer
        response = await web.respond(request)
        return response if response is not None else not_found()

    app.add_exception_handler(HTTPException, handle_http)  # type: ignore[arg-type]
    return web
