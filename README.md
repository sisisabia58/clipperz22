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
| `CLIPFORGE_COMPUTE` | Backend | `modal` (default) or `local` |
| `MODAL_GPU_BASE_URL` | Backend | Deployed Modal GPU web URL |
| `MODAL_PROXY_KEY` / `MODAL_PROXY_SECRET` | Backend | Modal proxy auth for GPU endpoints |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Backend | OAuth client for Google Drive |
| `GOOGLE_OAUTH_REDIRECT_URI` | Backend | Must match the Cloud Console redirect URI |
| `CLIPFORGE_WHISPER_DEVICE` | GPU worker | `cuda` on Modal, `cpu` locally |
| `CLIPFORGE_VIDEO_ENCODER` | GPU worker | `h264_nvenc` on Modal, `libx264` locally |

The first Whisper run downloads a model (default `Systran/faster-whisper-small`). Use `Systran/faster-whisper-base` if CPU is tight.

## Modal GPU (transcription and encoding)

ClipForge sends transcription, video encoding, face-aware crop, and clip export to **Modal GPU endpoints** instead of the local CPU. The Docker web app stays on CPU and calls those endpoints.

1. Install and log in to Modal:

```bash
pip install modal
modal setup
```

2. Deploy the GPU workers from this repo:

```bash
modal deploy backend/modal_app.py
```

3. Copy the printed `*.modal.run` URL into `.env`:

```env
CLIPFORGE_COMPUTE=modal
MODAL_GPU_BASE_URL=https://YOUR_WORKSPACE--clipforge-gpu-web.modal.run
MODAL_PROXY_KEY=wk-...
MODAL_PROXY_SECRET=ws-...
```

4. Restart Compose. `GET /api/health` should report `"compute": "modal"`.

Endpoints on the GPU app:

| Path | Role |
| --- | --- |
| `GET /health` | GPU worker health |
| `POST /transcribe` | faster-whisper on CUDA (`float16`) |
| `POST /encode` | vertical clip encode (`h264_nvenc` when available, else `libx264`) |
| `POST /jobs` | full download → transcribe → score → export pipeline |

If `MODAL_GPU_BASE_URL` is empty, the backend **falls back to local CPU** so the UI still runs without Modal credentials. Set `CLIPFORGE_COMPUTE=local` to force that path.

On the GPU worker, Whisper uses `device=cuda` and FFmpeg prefers NVENC. Face/person crop and subtitle burn run in the same Modal job.

## Google Drive

Use Drive as a source next to YouTube and local upload.

1. Create a Google Cloud OAuth **Web** client.
2. Add authorized redirect URI `http://127.0.0.1:43123/api/drive/callback` (or your public origin).
3. Set in `.env`:

```env
GOOGLE_CLIENT_ID=....apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=...
GOOGLE_OAUTH_REDIRECT_URI=http://127.0.0.1:43123/api/drive/callback
```

4. In the UI, choose **Drive**, connect, pick a video, optionally check **Auto-upload finished clips** and select a destination folder.
5. After clipping, MP4s remain under local `outputs/` and, if that checkbox is on, are copied to the Drive folder.

Without OAuth credentials, the Drive tab shows setup instructions and YouTube/upload keep working.

## Safety and legal notes

ClipForge is intended for local workflows and content you are allowed to process. Follow YouTube terms and applicable copyright law.

Do not expose the backend publicly without authentication, rate limits, request validation, quotas, and cleanup. The API accepts URLs and runs expensive jobs.

## Project structure

```text
backend/          FastAPI + clipper pipeline
backend/modal_app.py  Modal GPU endpoints (Whisper + NVENC + full jobs)
frontend/         Next.js UI
gateway/          nginx reverse proxy
docker-compose.yml
```

## License

MIT. See `LICENSE`. Original work by [mallexibra](https://mallexibra.my.id/). Third-party notices live in `NOTICE`.
