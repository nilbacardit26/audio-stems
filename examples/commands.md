# Command Examples

```bash
# Install user-wide command
./scripts/install-user-command.sh

# Interactive wizard with path completion, indexed @ search, and / commands
stems

# In the audio prompt, press Tab after direct paths, @ searches, or / commands.
# Examples: /help, /reindex, /install-separator, /mnt/music/song.mp3, @kill, @Music.*kill
# Up/Down moves through results; Right accepts the highlighted result.
# By default @ searches under $HOME and caches results in ~/.cache/audio-stems.
# Use Ctrl+Left / Ctrl+Right to jump through long path segments.

# Same wizard, explicit command
stems interactive

# Show the built-in preset menu
stems presets

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
  --separator-model bs-roformer

# In interactive mode, the separator preset lets you choose common model aliases:
# inst-hq, voc-ft, or bs-roformer.
```
