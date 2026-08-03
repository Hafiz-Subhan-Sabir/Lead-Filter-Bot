from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import init_db
from routers import filter, profiles

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Lead Filter Bot",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(profiles.router)
app.include_router(filter.router)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def home():
    return FileResponse(FRONTEND_DIR / "index.html")
