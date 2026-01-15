# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

claude-fx-plugin is a Claude Code plugin that displays a persistent animated mascot overlay beside your terminal. The overlay reacts to Claude's activity in real-time - showing different states for greeting, working, success, error, and celebration.

**Key Feature**: True transparency using PyObjC native macOS NSWindow - the character floats with no background window visible.

## Architecture

```
Claude Code Hooks → hook-handler.py → ~/.claude-fx/state.json → overlay.py (PyObjC)
                         ↓
                   setup.py (on SessionStart)
```

1. **SessionStart** triggers setup check (installs deps if needed)
2. **hook-handler.py** maps hook events to states, writes state file
3. **overlay.py** polls state file, displays transparent PNG/GIF overlay

## Directory Structure

```
claude-fx-plugin/
├── .claude-plugin/
│   └── plugin.json           # Plugin manifest for Claude Code
├── hooks/
│   └── hooks.json            # Hook → handler mappings
├── scripts/
│   ├── hook-handler.py       # Receives hooks, writes state, plays sounds
│   ├── overlay.py            # PyObjC transparent overlay (macOS)
│   └── setup.py              # Dependency checker and installer
├── commands/
│   └── setup.md              # /claude-fx:setup slash command
├── themes/
│   └── default/
│       ├── manifest.json     # State → asset mappings
│       ├── characters/       # PNG images per state
│       └── sounds/           # WAV audio files
├── settings-fx.json          # User configuration
└── CLAUDE.md
```

## Key Files

### scripts/overlay.py (PyObjC)
- **Native macOS NSWindow** with true transparency
- `NSColor.clearColor()` for invisible background
- Click-through enabled (`setIgnoresMouseEvents_`)
- Reads settings from `settings-fx.json`
- Polls `~/.claude-fx/state.json` via NSTimer
- Terminal position detection via Quartz API
- PID file at `~/.claude-fx/overlay.pid`

### scripts/hook-handler.py
- Entry point for all Claude Code hooks
- Reads JSON from stdin (hook event data)
- Maps hook events to overlay states
- Writes state to `~/.claude-fx/state.json`
- Auto-starts overlay if not running
- Plays sounds via `afplay` with configurable volume
- Runs setup check on SessionStart
- Always exits 0 (never blocks Claude)

### scripts/setup.py
- Checks all dependencies on SessionStart
- Detects Homebrew Python, adds `--break-system-packages`
- Shows colorful terminal output with install commands
- Creates `~/.claude-fx/setup_ok` when complete
- Can auto-install with `--install` flag

### settings-fx.json
```json
{
  "overlay": {
    "enabled": true,
    "maxHeight": 350,
    "position": "auto",
    "customX": null,
    "customY": null,
    "offsetX": 20,
    "offsetY": 40
  },
  "audio": {
    "enabled": true,
    "volume": 0.5
  },
  "theme": "default"
}
```

## State Machine

| State | Trigger | Description |
|-------|---------|-------------|
| idle | Default | Relaxed pose |
| greeting | SessionStart | Waving hello |
| working | PreToolUse | Focused/busy |
| success | PostToolUse (ok) | Thumbs up |
| error | PostToolUse (fail) | Worried |
| celebrating | Stop | Victory pose |
| sleeping | Extended idle | Zzz |

## Hook Events

| Event | When Fired | Maps To |
|-------|------------|---------|
| `SessionStart` | Session begins | greeting |
| `PreToolUse` | Before tool | working |
| `PostToolUse` | After tool | success/error |
| `Stop` | Response complete | celebrating |

## Dependencies

Required (auto-detected by setup.py):
- **Python 3.9+** - Core runtime
- **Pillow** - Image processing (`pip3 install pillow`)
- **tkinter** - Fallback GUI (`brew install python-tk@3.x`)
- **pyobjc-framework-Quartz** - Terminal detection + NSWindow
- **pyobjc-framework-Cocoa** - Native macOS UI

## Commands

```bash
# Run setup check
python3 scripts/setup.py --force

# Auto-install missing deps
python3 scripts/setup.py --force --install

# Start overlay manually
CLAUDE_FX_ROOT="$(pwd)" python3 scripts/overlay.py &

# Test state changes
echo '{"state": "greeting"}' > ~/.claude-fx/state.json

# Stop overlay
pkill -f overlay.py

# Clear setup status (re-run checks)
rm ~/.claude-fx/setup_ok
```

## Custom Characters

Replace PNGs in `themes/default/characters/`:
- idle.png, greeting.png, working.png
- success.png, error.png, celebrating.png, sleeping.png

Requirements:
- **PNG with transparent background** (RGBA)
- Any size (scaled to maxHeight setting)
- GIFs also supported (animated)

## Environment Variables

| Variable | Description |
|----------|-------------|
| `CLAUDE_PLUGIN_ROOT` | Plugin directory (set by Claude) |
| `CLAUDE_FX_ROOT` | Alternative for overlay.py |

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| macOS | Full | PyObjC + Quartz |
| Linux | Partial | Needs X11 work |
| Windows | Not supported | - |

## Recent Changes

- **PyObjC overlay** - True transparency, no window chrome
- **Setup system** - Auto-detects and helps install dependencies
- **Configurable settings** - Size, position, volume
- **PNG support** - High-quality transparent images
- **Waifu mascot** - Custom anime-style character included
