from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import init_db
from routers import filter, profiles

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# Init DB at import time (more reliable than lifespan under a2wsgi on PythonAnywhere)
init_db()

app = FastAPI(
    title="Lead Filter Bot",
    version="0.1.0",
)

app.include_router(profiles.router)
app.include_router(filter.router)

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def home():
    return FileResponse(FRONTEND_DIR / "index.html")
