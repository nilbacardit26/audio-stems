# AGENTS.md

## Project Scope
This repository contains a small local CLI wrapper for audio stem separation.

## Boundaries
- Keep the wrapper lightweight; heavy ML dependencies should stay optional and
  installed into the local `.venv`.
- Do not commit generated stems, downloaded model weights, source audio, or local caches.
- Prefer Demucs as the default engine and keep audio-separator support as an optional advanced path.

## Validation
- Run `uv run stems --help` after CLI changes.
- Run `uv run stems doctor` when touching runtime detection.
- Run `uv run stems interactive --help` and a PTY smoke test when touching interactive prompts.
- Use `stems --dry-run ...` for command generation tests when no audio fixture is available.

## Git
- Commits should be scoped to this repository only.
- No secrets or private audio files in Git.
