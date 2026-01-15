# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

claude-fx-plugin is a Claude Code plugin that displays a persistent animated overlay beside your terminal. The overlay reacts to Claude's activity - showing different animations for working, success, error, and celebration states.

## Architecture

```
Claude Code → hook-handler.py → ~/.claude-fx/state.json → overlay.py
```

1. **Hooks fire** (SessionStart, PreToolUse, PostToolUse, Stop)
2. **hook-handler.py** maps event to state, writes to state file, starts overlay
3. **overlay.py** polls state file every 100ms, updates displayed GIF

## Directory Structure

```
claude-fx-plugin/
├── .claude-plugin/
│   └── plugin.json           # Plugin manifest
├── hooks/
│   └── hooks.json            # Hook → handler mappings
├── scripts/
│   ├── hook-handler.py       # Receives hooks, writes state
│   ├── overlay.py            # Persistent tkinter overlay
│   └── generate-placeholders.py  # Creates default GIFs
├── themes/
│   └── default/
│       ├── manifest.json     # State → asset mappings
│       ├── characters/       # GIF animations per state
│       └── sounds/           # Audio files
├── settings-fx.json          # User configuration
└── package.json              # npm scripts for convenience
```

## Key Files

### scripts/hook-handler.py
- Entry point for all hooks
- Reads JSON from stdin (hook event data)
- Maps hook event to overlay state
- Writes state to `~/.claude-fx/state.json`
- Auto-starts overlay if not running
- Plays sound effects via `afplay` (macOS)
- Always exits with code 0 (never blocks Claude)

### scripts/overlay.py
- Persistent tkinter window with animated GIF
- Transparent background, always-on-top
- Polls state file every 100ms
- Positions next to terminal (Quartz API on macOS)
- PID file at `~/.claude-fx/overlay.pid`

### hooks/hooks.json
Maps Claude Code events to hook-handler.py:
- SessionStart → greeting state
- PreToolUse → working state
- PostToolUse → success/error state
- Stop → celebrating state

## State Machine

| State | Trigger | Animation |
|-------|---------|-----------|
| idle | Default | Gentle breathing |
| greeting | SessionStart | Waving |
| working | PreToolUse | Spinning |
| success | PostToolUse (ok) | Bouncing |
| error | PostToolUse (fail) | Shaking |
| celebrating | Stop | Confetti |
| sleeping | 5min idle | Zzz |

## Claude Code Hook Events

| Event | When Fired | Stdin Contains |
|-------|------------|----------------|
| `SessionStart` | Session begins | `session_id` |
| `PreToolUse` | Before tool executes | `tool_name`, `tool_input` |
| `PostToolUse` | After tool completes | `tool_name`, `tool_result` |
| `Stop` | Agent finishes | `session_id` |

### Stdin JSON Format
```json
{
  "session_id": "abc123",
  "hook_event_name": "PreToolUse",
  "tool_name": "Write",
  "tool_input": { "file_path": "/path/to/file.js" }
}
```

## Commands

```bash
# Generate placeholder GIFs
python3 scripts/generate-placeholders.py

# Test overlay manually
python3 scripts/overlay.py &

# Simulate hook events
echo '{"hook_event_name": "PreToolUse"}' | python3 scripts/hook-handler.py

# Stop overlay
pkill -f overlay.py
```

## Dependencies

- Python 3.9+
- Pillow (PIL) for GIF handling
- tkinter (built-in) for overlay window
- Quartz (macOS) for terminal position detection

## Environment Variables

| Variable | Description |
|----------|-------------|
| `CLAUDE_PLUGIN_ROOT` | Absolute path to plugin directory |
| `CLAUDE_FX_ROOT` | Alternative for overlay.py |

## Adding Custom Characters

Replace GIFs in `themes/default/characters/`:
- idle.gif, greeting.gif, working.gif, success.gif
- error.gif, celebrating.gif, sleeping.gif
- Recommended: 150x150 pixels with transparent background

## Platform Support

- **macOS**: Full support (Quartz + afplay)
- **Linux**: Overlay works, terminal detection needs X11
- **Windows**: Not implemented
