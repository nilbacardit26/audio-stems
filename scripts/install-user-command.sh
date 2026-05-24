#!/usr/bin/env bash
set -euo pipefail

APP_HOME="$(cd "$(dirname "$0")/.." && pwd)"
BIN_DIR="${HOME}/.local/bin"
TARGET="${BIN_DIR}/stems"
APP_TARGET="${BIN_DIR}/stems-app"

mkdir -p "${BIN_DIR}"

cat > "${TARGET}" <<EOF
#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${APP_HOME}"
VENV_BIN="\${APP_HOME}/.venv/bin"
VENV_STEMS="\${APP_HOME}/.venv/bin/stems"

if [[ -x "\${VENV_STEMS}" ]]; then
  export PATH="\${VENV_BIN}:\${PATH}"
  exec "\${VENV_STEMS}" "\$@"
fi

if command -v uv >/dev/null 2>&1; then
  exec uv run --project "\${APP_HOME}" stems "\$@"
fi

echo "stems is not set up yet." >&2
echo "Install uv or run: \${APP_HOME}/scripts/setup.sh" >&2
exit 127
EOF

chmod 755 "${TARGET}"

cat > "${APP_TARGET}" <<EOF
#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${APP_HOME}"
exec "\${APP_HOME}/scripts/run-web.sh" "\$@"
EOF

chmod 755 "${APP_TARGET}"

echo "Installed ${TARGET}"
echo "Installed ${APP_TARGET}"
echo "Try: stems"
echo "Try: stems-app"
