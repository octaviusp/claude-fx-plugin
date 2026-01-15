# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

claude-fx-plugin is a Claude Code plugin that displays a persistent animated mascot overlay beside your terminal. The overlay reacts to Claude's activity in real-time - showing different states for greeting, working, success, error, and celebration.

**Key Feature**: True transparency using PyObjC native macOS NSWindow - the character floats with no background window visible.

## Architecture

```
Claude Code Hooks → hook-handler.py → Unix Socket → overlay.py (PyObjC)
                         ↓
                   setup.py (on SessionStart)
```

1. **SessionStart** triggers setup check (installs deps if needed)
2. **hook-handler.py** maps hook events to states, sends via Unix socket
3. **overlay.py** receives state updates via socket, displays transparent PNG/GIF overlay

**IPC**: Uses Unix domain sockets (`~/.claude-fx/sock-{SESSION_ID}.sock`) for fast, reliable inter-process communication with zero file I/O overhead.

## Directory Structure

```
claude-fx-plugin/
├── .claude-plugin/
│   └── plugin.json           # Plugin manifest for Claude Code
├── hooks/
│   └── hooks.json            # Hook → handler mappings
├── scripts/
│   ├── hook-handler.py       # Receives hooks, sends state via socket, plays sounds
│   ├── overlay.py            # PyObjC transparent overlay + socket server (macOS)
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
- **Unix socket server** - receives state updates via `~/.claude-fx/sock-{SESSION_ID}.sock`
- Terminal position detection via Quartz API
- **Terminal-specific visibility** - only shows when the terminal that started Claude Code is active
- **Fade animations** - smooth alpha transitions when showing/hiding
- **Parent process monitoring** - auto-exits when terminal closes

### scripts/hook-handler.py
- Entry point for all Claude Code hooks
- Reads JSON from stdin (hook event data)
- Maps hook events to overlay states
- **Detects terminal PID** - walks process tree to find parent terminal
- **Socket client** - sends state via Unix socket (zero file I/O)
- Auto-starts overlay if not running
- Plays sounds via `afplay` with configurable volume
- Runs setup check on SessionStart
- Cleans up legacy files on SessionStart
- Always exits 0 (never blocks Claude)

### scripts/setup.py
- Checks all dependencies on SessionStart
- Detects Homebrew Python, adds `--break-system-packages`
- Shows formatted terminal output with copy-paste install commands
- Creates `~/.claude-fx/setup_ok` when complete

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
    "offsetY": 40,
    "showOnlyWhenTerminalActive": true,
    "fadeAnimation": true
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
- **pyobjc-framework-Quartz** - Terminal detection + window positioning
- **pyobjc-framework-Cocoa** - Native macOS UI (NSWindow)

## Commands

```bash
# Run setup check
python3 scripts/setup.py --force

# Start overlay manually (requires CLAUDE_FX_SESSION)
CLAUDE_FX_ROOT="$(pwd)" CLAUDE_FX_SESSION=$$ python3 scripts/overlay.py &

# Check active sockets
ls ~/.claude-fx/sock-*.sock

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

## Sound System

Sound files in `themes/default/sounds/` named to match states:
- greeting.aiff, working.aiff, success.aiff
- error.aiff, celebrating.aiff, farewell.aiff

**Supported formats:** `.wav`, `.mp3`, `.aiff`, `.m4a`, `.caf`, `.aac`

Sound playback uses macOS native `afplay` command. Volume controlled via `audio.volume` setting (0.0-1.0).

Sound discovery priority:
1. Path specified in `manifest.json` (e.g., `"sound": "sounds/greeting.aiff"`)
2. File matching state name (e.g., `greeting.wav` for greeting state)

## Environment Variables

| Variable | Description |
|----------|-------------|
| `CLAUDE_PLUGIN_ROOT` | Plugin directory (set by Claude) |
| `CLAUDE_FX_ROOT` | Alternative for overlay.py |
| `CLAUDE_FX_SESSION` | Session ID (terminal PID) for socket path |

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| macOS | Full | PyObjC + Quartz |
| Linux | Partial | Needs X11 work |
| Windows | Not supported | - |

## Recent Changes

- **Sound system** - Multi-format audio with manifest-based or convention-based discovery
- **Visibility fixes** - Bulletproof terminal detection with notification observers
- **Unix Socket IPC** - Zero-latency state updates via Unix domain sockets
- **Parent process monitoring** - Overlay auto-exits when terminal closes
- **Session isolation** - Each terminal gets its own socket
- **Fade animations** - Smooth alpha transitions
- **Responsive sizing** - Scale overlay with terminal height
