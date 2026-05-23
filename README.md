# audio-stems

Local stem separation wrapper for this workstation. It gives you one command,
`stems`, while delegating the actual neural separation to local tools:

- Demucs for general music stems: vocals, drums, bass, other.
- audio-separator for optional UVR-style vocal/instrumental models.

No hosted provider is required.

## Hardware target

This setup is tuned for:

- NVIDIA RTX 4070, 12 GB VRAM
- AMD Ryzen 9 7950X
- 64 GB RAM
- Local NVMe SSD

## Install From GitHub With pip

This installs directly from GitHub. No PyPI release is required.

Install the lightweight CLI wrapper only:

```bash
python3 -m pip install --user "git+https://github.com/nilbacardit26/audio-stems.git"
```

For actual stem separation, install the CLI plus Demucs runtime dependencies:

```bash
python3 -m pip install --user \
  "audio-stems[demucs] @ git+https://github.com/nilbacardit26/audio-stems.git"
```

For NVIDIA/CUDA systems, install PyTorch CUDA wheels first, then install
`audio-stems`:

```bash
python3 -m pip install --user torch torchaudio \
  --index-url https://download.pytorch.org/whl/cu128
python3 -m pip install --user \
  "audio-stems[demucs] @ git+https://github.com/nilbacardit26/audio-stems.git"
```

Then run:

```bash
stems
```

If `stems` is not found, make sure `~/.local/bin` is in your `PATH`.

## Install From Source Checkout

Prerequisites:

- Python 3.10+
- `uv`
- `ffmpeg`
- NVIDIA GPU drivers for CUDA acceleration, or CPU mode as fallback

Clone and install the default local Demucs setup:

```bash
git clone https://github.com/nilbacardit26/audio-stems.git
cd audio-stems
./scripts/setup.sh
.venv/bin/stems doctor
```

Install the `stems` command for your user, so you can run it from any directory
without activating `.venv`:

```bash
./scripts/install-user-command.sh
stems
```

For CPU-only systems:

```bash
./scripts/setup.sh --cpu
./scripts/install-user-command.sh
```

For Demucs plus optional audio-separator/UVR models:

```bash
./scripts/setup.sh --full
./scripts/install-user-command.sh
```

## Quick Start

Start the interactive CLI:

```bash
stems
```

or:

```bash
stems interactive
stems i
```

The interactive mode uses a compact `›` prompt style and lets you choose:

- first-run setup if Demucs is missing and `scripts/setup.sh` is available
- local runtime visibility: `ffmpeg`, GPU, Demucs, optional audio-separator
- audio/video file(s), using direct path completion, local `/` search, or global `@` search
- preset/model
- output directory
- device
- final confirmation before processing

Audio file input supports direct path completion and `@` modes:

```text
/mnt/media/song.mp3   absolute path completion
~/Music/song.mp3      home path completion
/demo                 indexed media search under the current folder
/Videos               indexed media search under the current folder
@~/Music/song.mp3     path completion
@/mnt/media/song.mp3  absolute path completion
@Videos               indexed media search across paths
@beatles.*flac        regex search across audio paths
@live.*\.wav          regex search across audio paths
```

The first indexed `/` or `@` search builds an in-memory media-file index with
`rg --files` when available. Later searches in the same interactive session
filter that cache in memory, so terms like `/demo`, `@Videos`, and regexes like
`@beatles.*flac` stay fast.

While editing file or output paths:

```text
Ctrl+Left   jump to the previous path segment
Ctrl+Right  jump to the next path segment
```

By default, `@` indexed search scans `/` while excluding noisy system/cache folders.
To customize search roots:

```bash
export STEMS_SEARCH_ROOTS="$HOME/Music:/mnt/media:/media"
stems
```

Install `stems` as a user-wide command, so you do not need to activate `.venv`:

```bash
./scripts/install-user-command.sh
```

This installs a wrapper at `~/.local/bin/stems`.

Separate a track with the recommended quality preset:

```bash
stems song.mp3
```

Useful presets:

```bash
stems song.mp3 --preset demucs      # best default 4-stem quality
stems song.mp3 --preset fast        # faster 4-stem model
stems song.mp3 --preset vocals      # vocals + no_vocals
stems song.mp3 --preset six         # experimental vocals/drums/bass/other/guitar/piano
```

Outputs go to `separated/` by default.

## Optional audio-separator setup

Install the optional engine when you want to try UVR/MDX/RoFormer models:

From a source checkout:

```bash
./scripts/setup.sh --full
stems models --filter vocals
```

From the GitHub/pip install:

```bash
python3 -m pip install --user --upgrade \
  "audio-stems[all] @ git+https://github.com/nilbacardit26/audio-stems.git"
stems models --filter vocals
```

Then run a specific model:

```bash
stems song.mp3 --preset separator --separator-model UVR-MDX-NET-Inst_HQ_3.onnx
```

Or a stronger BS-RoFormer vocal/instrumental example:

```bash
stems song.mp3 --preset separator --separator-model model_bs_roformer_ep_317_sdr_12.9755.ckpt
```

The audio-separator package downloads selected model weights automatically into
`models/audio-separator/`.

## Common commands

Dry-run command generation:

```bash
stems song.mp3 --preset demucs --dry-run
```

Interactive selection:

```bash
stems
```

Use CPU explicitly:

```bash
stems song.mp3 --device cpu
```

Write FLAC from audio-separator:

```bash
stems song.mp3 --preset separator --separator-model UVR-MDX-NET-Inst_HQ_3.onnx --format FLAC
```

## Git

This repo ignores generated audio, model weights, and the local virtualenv.

```bash
git status
git add .
git commit -m "Create local audio stems wrapper"
git remote add origin git@github.com:<you>/audio-stems.git
git push -u origin main
```
