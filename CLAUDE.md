# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

claude-fx-plugin is a Claude Code plugin that displays a persistent animated mascot overlay beside your terminal. The overlay reacts to Claude's activity in real-time - showing different states for greeting, working, success, error, and celebration.

**Key Features**:
- True transparency using PyObjC native macOS NSWindow
- Floating animation with glowing aura effect
- Bottom gradient fade for text readability
- Multi-instance support (multiple terminals simultaneously)
- Session isolation via shell PID

## Architecture

```
Claude Code Hooks → hook-handler.py → Unix Socket → overlay.py (PyObjC)
                         ↓
                   setup.py (on SessionStart)
```

1. **SessionStart** triggers setup check (installs deps if needed)
2. **hook-handler.py** maps hook events to states, sends via Unix socket
3. **overlay.py** receives state updates via socket, displays transparent PNG overlay

**IPC**: Uses Unix domain sockets (`~/.claude-fx/sock-{SHELL_PID}.sock`) for fast, reliable inter-process communication. Each shell session gets its own socket for multi-instance support.

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
│   ├── setup.md              # /claude-fx:setup slash command
│   ├── change-fx.md          # /claude-fx:change-fx customization guide
│   ├── change-character.md   # /claude-fx:change-character switch characters
│   └── clean-fx.md           # /claude-fx:clean-fx emergency cleanup
├── themes/
│   └── default/
│       ├── manifest.json     # State → asset mappings
│       ├── characters/       # PNG images per state
│       └── sounds/           # Audio files
├── settings-fx.json          # User configuration
└── CLAUDE.md
```

## Key Files

### scripts/overlay.py (PyObjC)
- **Native macOS NSWindow** with true transparency
- `NSColor.clearColor()` for invisible background
- Click-through enabled (`setIgnoresMouseEvents_`)
- Reads settings from `settings-fx.json`
- **Unix socket server** - receives state updates via `~/.claude-fx/sock-{SHELL_PID}.sock`
- Terminal position detection via Quartz API
- **Terminal-specific visibility** - only shows when the terminal that started Claude Code is active
- **Fade animations** - smooth alpha transitions when showing/hiding
- **Parent process monitoring** - auto-exits when terminal closes
- **Floating animation** - subtle vertical bobbing motion
- **Aura glow effect** - pulsing shadow around character
- **Bottom gradient** - fades image bottom for text readability

### scripts/hook-handler.py
- Entry point for all Claude Code hooks
- Reads JSON from stdin (hook event data)
- Maps hook events to overlay states
- **Detects shell PID** - walks process tree to find shell (unique per terminal window)
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
    "responsive": true,
    "heightRatio": 1,
    "maxHeight": 750,
    "customX": null,
    "customY": null,
    "offsetX": 20,
    "offsetY": 0,
    "showOnlyWhenTerminalActive": true,
    "fadeAnimation": true,
    "bottomGradient": {
      "enabled": true,
      "percentage": 0.8
    }
  },
  "audio": {
    "enabled": true,
    "volume": 0.5
  },
  "theme": "default"
}
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `overlay.enabled` | bool | true | Show/hide overlay |
| `overlay.responsive` | bool | true | Scale with terminal height |
| `overlay.heightRatio` | float | 1.0 | Ratio of terminal height (0.0-1.0) |
| `overlay.maxHeight` | int | 750 | Maximum image height in pixels |
| `overlay.customX/Y` | int | null | Fixed position coordinates |
| `overlay.offsetX/Y` | int | 20/0 | Offset from terminal edge |
| `overlay.showOnlyWhenTerminalActive` | bool | true | Hide when terminal loses focus |
| `overlay.fadeAnimation` | bool | true | Smooth show/hide transitions |
| `overlay.bottomGradient.enabled` | bool | true | Fade bottom of image |
| `overlay.bottomGradient.percentage` | float | 0.8 | Portion to fade (0.0-1.0) |
| `audio.enabled` | bool | true | Enable sound effects |
| `audio.volume` | float | 0.5 | Volume level (0.0-1.0) |
| `theme` | string | "default" | Theme folder name |

## State Machine

| State | Trigger | Duration | Description |
|-------|---------|----------|-------------|
| idle | Default | permanent | Relaxed pose |
| greeting | SessionStart | 3.0s | Waving hello |
| working | PreToolUse | permanent | Focused/busy |
| success | PostToolUse (ok) | 3.0s | Thumbs up |
| error | PostToolUse (fail) | 3.0s | Worried |
| celebrating | Stop | 3.0s | Victory pose |
| sleeping | Extended idle | permanent | Zzz |
| farewell | SessionEnd | 3.0s | Wave goodbye (then shutdown) |

## Hook Events

| Event | When Fired | Maps To |
|-------|------------|---------|
| `SessionStart` | Session begins | greeting |
| `PreToolUse` | Before tool | working |
| `PostToolUse` | After tool | success/error |
| `Stop` | Response complete | celebrating |
| `SessionEnd` | Session ends | farewell |

## Animation System

### Floating Effect
```python
FLOAT_AMPLITUDE = 3.0   # pixels of vertical movement
FLOAT_PERIOD = 2.5      # seconds for full oscillation cycle
```

### Aura Glow
```python
AURA_COLOR = (0.4, 0.55, 1.0, 1.0)  # Soft blue (R, G, B, A)
AURA_MIN_RADIUS = 8.0
AURA_MAX_RADIUS = 14.0
AURA_PERIOD = 1.8       # seconds for pulse cycle
AURA_OPACITY = 0.5
```

### Bottom Gradient
Applied via PIL before display. Multiplies alpha channel by a gradient that goes from 1.0 (full opacity) at `start_y` to 0.0 (transparent) at the bottom.

## Multi-Instance Architecture

Each terminal window gets its own overlay instance:

1. **Session ID** = Shell PID (unique per terminal window, even in same terminal app)
2. **Socket path** = `~/.claude-fx/sock-{SHELL_PID}.sock`
3. **PID file** = `~/.claude-fx/pid-{SHELL_PID}.txt`

This allows multiple Claude Code sessions to run simultaneously with independent overlays.

## Dependencies

Required (auto-detected by setup.py):
- **Python 3.9+** - Core runtime
- **Pillow** - Image processing (gradient, resize)
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

# Change character folder (session-specific)
python3 scripts/hook-handler.py change-character characters2

# Emergency cleanup
pkill -f 'python3.*overlay.py'
rm -f ~/.claude-fx/sock-*.sock ~/.claude-fx/pid-*.txt
```

## Custom Characters

Replace PNGs in `themes/default/characters/`:
- idle.png, greeting.png, working.png
- success.png, error.png, celebrating.png, sleeping.png

Requirements:
- **PNG with transparent background** (RGBA)
- Any size (scaled to maxHeight setting)

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
| `CLAUDE_FX_SESSION` | Session ID (shell PID) for socket path |

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| macOS | Full | PyObjC + Quartz |
| Linux | Not supported | Would need GTK/Qt port |
| Windows | Not supported | - |

## Recent Changes (v1.0.0)

- **Multi-instance support** - Run multiple Claude Code sessions with independent overlays
- **Shell PID isolation** - Session ID uses shell PID (unique per window) instead of terminal app PID
- **Bottom gradient fade** - Configurable alpha gradient at image bottom for text readability
- **Floating animation** - Subtle vertical bobbing motion (3px amplitude, 2.5s period)
- **Aura glow effect** - Pulsing blue shadow around character
- **Responsive sizing** - Scale overlay with terminal height via heightRatio
- **Sound system** - Multi-format audio with manifest-based or convention-based discovery
- **Bulletproof visibility** - NSWorkspace notifications + validation timer + Space change detection
- **Unix Socket IPC** - Zero-latency state updates via Unix domain sockets
- **Parent process monitoring** - Overlay auto-exits when terminal closes
- **Fade animations** - Smooth alpha transitions when showing/hiding
- **Signal handlers** - Clean shutdown on SIGTERM, SIGINT, SIGHUP
