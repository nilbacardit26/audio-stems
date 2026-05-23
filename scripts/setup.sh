#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/setup.sh [--full] [--cpu]

Creates .venv and installs the local stems CLI.

Options:
  --full  Install Demucs plus audio-separator GPU extras.
  --cpu   Skip CUDA PyTorch wheels and install CPU-compatible packages.
EOF
}

FULL=0
CPU=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --full)
      FULL=1
      shift
      ;;
    --cpu)
      CPU=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it first: https://docs.astral.sh/uv/" >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is required for most input formats." >&2
  echo "Install on Ubuntu/Debian with: sudo apt install ffmpeg" >&2
  exit 1
fi

cd "$(dirname "$0")/.."

if [[ ! -d .venv ]]; then
  uv venv --python 3.10
else
  echo "Reusing existing .venv"
fi
source .venv/bin/activate

if [[ "$CPU" -eq 0 ]] && command -v nvidia-smi >/dev/null 2>&1; then
  echo "Installing PyTorch CUDA 12.8 wheels..."
  uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
else
  echo "Installing default PyTorch wheels..."
  uv pip install torch torchaudio
fi

if [[ "$FULL" -eq 1 ]]; then
  uv pip install -e '.[all]'
else
  uv pip install -e '.[demucs]'
fi

echo
echo "Setup complete."
echo "Activate with: source .venv/bin/activate"
echo "Check with:    stems doctor"
