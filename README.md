# ClipForge

Docker-based web app for turning long YouTube videos into ready-to-post vertical clips. Paste a URL or upload a file, transcribe locally with faster-whisper, score clip candidates, and export 9:16 MP4s with burned-in subtitles.

Based on the open-source [mallexibra-dev/clipforge](https://github.com/mallexibra-dev/clipforge) project (MIT).

## What you get

- One public URL through an nginx gateway (frontend + API + generated videos).
- Download a YouTube video with `yt-dlp`, or upload MP4/MOV/MKV/WebM.
- Local transcription with `faster-whisper`.
- Automatic clip scoring and 9:16 export with SRT files.
- Burned-in captions, center crop, or face/person-aware crop.
- Optional OpenAI-compatible LLM for titles, captions, and hashtags.
- Job history in a Next.js UI.

## Quick start with Docker

You only need Docker and Docker Compose.

```bash
cp .env.docker.example .env
docker compose --env-file .env up --build
```

Open [http://127.0.0.1:43123](http://127.0.0.1:43123).

The gateway proxies:

| Path | Service |
| --- | --- |
| `/` | Next.js UI |
| `/api/*` | FastAPI job API |
| `/outputs/*` | generated clips and thumbnails |

Data lives in Docker volumes (`clipforge-data` for jobs/outputs, `clipforge-models` for Whisper/Hugging Face caches). Change the published port with `APP_PORT` in `.env`.

Stop with `docker compose down`. Add `-v` only if you also want to delete generated clips and downloaded models.

## Local development without Docker

Requirements: Python 3.12+, Node.js 22+, ffmpeg.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn api:app --host 127.0.0.1 --port 8010
```

In another terminal:

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open [http://127.0.0.1:43123](http://127.0.0.1:43123). The Next.js app proxies `/api` and `/outputs` to the backend.

CLI without the UI:

```bash
cd backend
source .venv/bin/activate
python clipper.py "https://www.youtube.com/watch?v=..." --top 5 --min 35 --max 180
```

Quick test on the first 180 seconds:

```bash
python clipper.py "https://www.youtube.com/watch?v=..." --model Systran/faster-whisper-base --analyze-seconds 180 --top 1
```

## API

```text
GET    /api/health
POST   /api/jobs
GET    /api/jobs
GET    /api/jobs/{job_id}
DELETE /api/jobs
POST   /api/uploads
GET    /api/probe
POST   /api/models
GET    /outputs/<generated-file>
```

## Configuration

| Variable | Where | Purpose |
| --- | --- | --- |
| `APP_PORT` | Compose | Host port for the nginx gateway (default `43123`) |
| `NEXT_PUBLIC_API_BASE` | Frontend | Browser API origin. Leave empty behind the gateway |
| `BACKEND_API_BASE` | Frontend | Server-side backend URL for Next.js rewrites |
| `DATA_DIR` | Backend | Jobs, uploads, and outputs directory |
| `CORS_ORIGINS` | Backend | Comma-separated origins, or `*` in Docker |
| `IN_DOCKER` | Backend | Rewrites `localhost` LLM URLs to `host.docker.internal` |

The first Whisper run downloads a model (default `Systran/faster-whisper-small`). Use `Systran/faster-whisper-base` if CPU is tight.

## Safety and legal notes

ClipForge is intended for local workflows and content you are allowed to process. Follow YouTube terms and applicable copyright law.

Do not expose the backend publicly without authentication, rate limits, request validation, quotas, and cleanup. The API accepts URLs and runs expensive jobs.

## Project structure

```text
backend/          FastAPI + clipper pipeline
frontend/         Next.js UI
gateway/          nginx reverse proxy
docker-compose.yml
```

## License

MIT. See `LICENSE`. Original work by [mallexibra](https://mallexibra.my.id/). Third-party notices live in `NOTICE`.
