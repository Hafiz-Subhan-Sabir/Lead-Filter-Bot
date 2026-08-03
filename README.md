# Lead Filter Bot

Paste messages → AI labels them against your intent → see matches in a web UI.

## Setup

```bash
cd lead-filter-bot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set your `OPENAI_API_KEY`.

## Run locally

```bash
cd backend
uvicorn main:app --reload
```

Open **http://127.0.0.1:8000/** (UI) or `/docs` (API).

## Deploy on PythonAnywhere

1. Upload the `lead-filter-bot` folder (or pull from git).
2. Create a virtualenv and `pip install -r requirements.txt`.
3. Add your `.env` next to the project (or set env vars in the web app).
4. Point the WSGI file at FastAPI, for example with uvicorn workers via ASGI, or use a simple `wsgi.py` wrapper if you use a supported ASGI setup.
5. Working directory should be `backend/` so imports resolve (`main:app`).
6. Ensure `frontend/` is on the server next to `backend/` (paths are relative).

API docs stay at `/docs`. UI is `/`.
