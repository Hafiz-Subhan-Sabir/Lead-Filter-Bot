from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from database import init_db
from routers import filter, profiles

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

init_db()

app = FastAPI(
    title="Lead Filter Bot",
    version="0.2.0",
)

app.include_router(profiles.router)
app.include_router(filter.router)
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.exception_handler(Exception)
async def unhandled_error(_request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}"},
    )


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def home():
    return FileResponse(FRONTEND_DIR / "index.html")
