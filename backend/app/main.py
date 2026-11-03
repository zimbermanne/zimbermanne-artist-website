import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

import asyncio

from . import catalog, config
from .database import Base, SessionLocal, engine
from .migrate import add_missing_columns
from .sync import runner
from .models import AdminUser, Track
from .routers import admin, auth, public
from .security import hash_password

log = logging.getLogger("zimbermanne")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    added_cols = add_missing_columns(engine)
    if added_cols:
        log.warning("Added columns: %s", ", ".join(added_cols))
    with SessionLocal() as db:
        added = catalog.seed_catalog(db)
        if added:
            log.warning("Seeded %s songs from music.json", added)
        if config.ADMIN_EMAIL and config.ADMIN_PASSWORD:
            user = db.scalar(select(AdminUser).where(AdminUser.email == config.ADMIN_EMAIL))
            if not user:
                db.add(AdminUser(email=config.ADMIN_EMAIL, password_hash=hash_password(config.ADMIN_PASSWORD)))
                db.commit()
                log.warning("Created admin user %s", config.ADMIN_EMAIL)
        elif not db.scalar(select(AdminUser).limit(1)):
            log.warning("No admin user yet: set ADMIN_EMAIL and ADMIN_PASSWORD and restart.")
    task = asyncio.create_task(runner.scheduler())
    yield
    task.cancel()


app = FastAPI(title="Zimbermanne API", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(GZipMiddleware, minimum_size=800)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(public.router)
app.include_router(auth.router)
app.include_router(admin.router)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/robots.txt", include_in_schema=False)
def robots():
    return PlainTextResponse(f"User-agent: *\nAllow: /\nDisallow: /admin\nSitemap: {config.SITE_URL}/sitemap.xml\n")


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap():
    with SessionLocal() as db:
        slugs = [t.slug for t in db.scalars(select(Track).order_by(Track.id))]
    urls = [f"{config.SITE_URL}/"] + [f"{config.SITE_URL}/song/{s}" for s in slugs]
    body = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>',
                    media_type="application/xml")


# ---- serve the built React app (production: one Railway service) ----
DIST = config.FRONTEND_DIST
if (DIST / "index.html").exists():
    if (DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str, request: Request):
        if path.startswith(("api/", "download/")):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        f = (DIST / path).resolve()
        if path and f.is_file() and DIST.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
