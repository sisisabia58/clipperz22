# Contributing

Thanks for improving ClipForge.

## Docker

```bash
cp .env.docker.example .env
docker compose --env-file .env up --build
```

Open `http://127.0.0.1:43123`.

## Local setup

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn api:app --host 127.0.0.1 --port 8010
```

Frontend:

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open `http://127.0.0.1:43123`.

## Checks

Run these before sending a change:

```bash
python -m py_compile backend/api.py backend/clipper.py backend/llm.py
cd backend && python -m pytest
cd frontend && npm run build
```

## Pull requests

- Keep changes focused.
- Include screenshots or short notes for UI changes.
- Mention tested commands.
- Do not commit generated clips, local outputs, `.env` files, or `jobs.json`.
