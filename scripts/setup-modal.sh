#!/usr/bin/env bash
# Deploy ClipForge GPU workers to Modal and print Railway env vars to set.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v modal >/dev/null 2>&1; then
  echo "Installing Modal CLI..."
  python3 -m pip install --user modal
  export PATH="$HOME/.local/bin:$PATH"
fi

if ! modal profile current >/dev/null 2>&1; then
  echo "Run: modal setup"
  exit 1
fi

echo "Deploying ClipForge GPU app to Modal..."
modal deploy backend/modal_app.py

echo
echo "Creating a proxy auth token (shown once — save it now)..."
TOKEN_JSON="$(modal workspace proxy-tokens create --json)"
MODAL_KEY="$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d['Modal-Key'])" <<<"$TOKEN_JSON")"
MODAL_SECRET="$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d['Modal-Secret'])" <<<"$TOKEN_JSON")"

echo
echo "Copy the *.modal.run URL from the deploy output above, then set these on Railway:"
echo
echo "  CLIPFORGE_COMPUTE=modal"
echo "  MODAL_GPU_BASE_URL=<your-workspace--clipforge-gpu-web.modal.run URL>"
echo "  MODAL_PROXY_KEY=$MODAL_KEY"
echo "  MODAL_PROXY_SECRET=$MODAL_SECRET"
echo
echo "Railway CLI example:"
echo "  railway variable set CLIPFORGE_COMPUTE=modal MODAL_GPU_BASE_URL=<url> MODAL_PROXY_KEY=$MODAL_KEY MODAL_PROXY_SECRET=$MODAL_SECRET --service clipperz22"
echo
echo "Verify after redeploy:"
echo "  curl https://clipperz22-production.up.railway.app/api/health"
echo "  # should report \"compute\": \"modal\""
