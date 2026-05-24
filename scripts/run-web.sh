#!/usr/bin/env bash
set -euo pipefail

APP_HOME="$(cd "$(dirname "$0")/.." && pwd)"
WEB_HOME="${APP_HOME}/web"

if [[ ! -f "${WEB_HOME}/dist/index.html" ]]; then
  if ! command -v npm >/dev/null 2>&1; then
    echo "npm is required to build the web app." >&2
    exit 127
  fi

  echo "Building web app..."
  if [[ ! -d "${WEB_HOME}/node_modules" ]]; then
    npm --prefix "${WEB_HOME}" install
  fi
  npm --prefix "${WEB_HOME}" run build
fi

if command -v stems >/dev/null 2>&1; then
  exec stems web "$@"
fi

exec uv run --project "${APP_HOME}" stems web "$@"
