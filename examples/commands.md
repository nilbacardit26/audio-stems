# Command Examples

```bash
# Install user-wide command
./scripts/install-user-command.sh

# Interactive wizard with path completion, local / search, and indexed @ search
stems

# In the audio prompt, press Tab after direct paths or @ searches
# Examples: /demo, /Videos, /mnt/music/song.mp3, @Videos, @beatles.*flac
# Use Ctrl+Left / Ctrl+Right to jump through long path segments.

# Same wizard, explicit command
stems interactive

# Recommended default
stems ~/Music/song.mp3

# Faster model
stems ~/Music/song.mp3 --preset fast

# Vocals and no_vocals only
stems ~/Music/song.mp3 --preset vocals

# Experimental six-stem model
stems ~/Music/song.mp3 --preset six

# Inspect the generated Demucs command
stems ~/Music/song.mp3 --dry-run

# List optional audio-separator vocal models
stems models --filter vocals

# Run one audio-separator model
stems ~/Music/song.mp3 \
  --preset separator \
  --separator-model model_bs_roformer_ep_317_sdr_12.9755.ckpt
```
