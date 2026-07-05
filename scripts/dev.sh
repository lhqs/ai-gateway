#!/usr/bin/env bash
set -euo pipefail

# 项目根目录（脚本上级目录的上级）
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

BACKEND_PORT="${BACKEND_PORT:-8004}"

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo
  echo "Shutting down..."
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "==> Starting backend (uvicorn on :$BACKEND_PORT)..."
(
  cd "$BACKEND_DIR"
  uv run uvicorn app.main:app --reload --port "$BACKEND_PORT"
) &
BACKEND_PID=$!

echo "==> Starting frontend (vite)..."
(
  cd "$FRONTEND_DIR"
  npm run dev
) &
FRONTEND_PID=$!

echo
echo "Backend  PID: $BACKEND_PID  (http://localhost:$BACKEND_PORT)"
echo "Frontend PID: $FRONTEND_PID"
echo "Press Ctrl+C to stop both."

wait
