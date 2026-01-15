# claude-fx-plugin

Persistent animated overlay companion for Claude Code. A cute mascot lives beside your terminal and reacts to Claude's activity - greeting you on session start, showing work in progress, celebrating successes, and more.

## Features

- **Persistent Overlay** - Character stays on screen beside your terminal
- **State-Based Animations** - Different GIFs for idle, working, success, error, etc.
- **Sound Effects** - Audio feedback for state changes
- **Terminal-Aware** - Automatically positions next to your terminal window
- **Easy Customization** - Drop in your own GIFs for custom mascots/waifus

## How It Works

```
Claude Code Hook → hook-handler.py → state.json → overlay.py (persistent window)
```

1. Claude Code fires hooks (SessionStart, PreToolUse, PostToolUse, Stop)
2. `hook-handler.py` maps the event to a state and writes to `~/.claude-fx/state.json`
3. `overlay.py` polls the state file and updates the displayed GIF
4. The overlay window persists beside your terminal

## States

| State | Trigger | Animation |
|-------|---------|-----------|
| `idle` | Default | Gentle breathing |
| `greeting` | SessionStart | Waving hello |
| `working` | PreToolUse | Spinning/busy |
| `success` | PostToolUse (ok) | Bouncing celebration |
| `error` | PostToolUse (fail) | Worried shake |
| `celebrating` | Stop | Party with confetti |
| `sleeping` | After 5min idle | Zzz animation |

## Installation

### Prerequisites

- Python 3.9+
- Pillow library: `pip install pillow`
- macOS (for terminal detection via Quartz)

### Setup

1. Clone to your plugins directory:
   ```bash
   git clone https://github.com/YOUR_USERNAME/claude-fx-plugin ~/.claude/plugins/claude-fx-plugin
   ```

2. Install Python dependency:
   ```bash
   pip install pillow
   ```

3. Generate placeholder GIFs (or add your own):
   ```bash
   cd ~/.claude/plugins/claude-fx-plugin
   python3 scripts/generate-placeholders.py
   ```

4. Enable the plugin in Claude Code

## Custom Characters

Replace the GIFs in `themes/default/characters/` with your own:

```
themes/default/characters/
├── idle.gif        # Default state
├── greeting.gif    # Session start
├── working.gif     # Tool execution
├── success.gif     # Task completed
├── error.gif       # Something failed
├── celebrating.gif # Major milestone
└── sleeping.gif    # Extended idle
```

GIF requirements:
- Recommended size: 150x150 pixels
- Transparent background works best
- Any frame rate (duration stored in GIF)

## Configuration

Edit `settings-fx.json`:

```json
{
  "overlay": {
    "enabled": true,
    "size": 150,
    "position": "terminal-right",
    "offsetX": 20,
    "offsetY": 40
  },
  "audio": {
    "enabled": true,
    "volume": 0.5
  }
}
```

## Manual Testing

Test the overlay manually:

```bash
# Start overlay
python3 scripts/overlay.py &

# Simulate hook events
echo '{"hook_event_name": "SessionStart"}' | python3 scripts/hook-handler.py
echo '{"hook_event_name": "PreToolUse", "tool_name": "Write"}' | python3 scripts/hook-handler.py
echo '{"hook_event_name": "Stop"}' | python3 scripts/hook-handler.py

# Stop overlay
pkill -f overlay.py
```

## Platform Support

- **macOS**: Full support (Quartz for terminal detection, afplay for audio)
- **Linux**: Partial (overlay works, terminal detection needs X11)
- **Windows**: Not yet supported

## Project Structure

```
claude-fx-plugin/
├── .claude-plugin/
│   └── plugin.json           # Plugin manifest
├── hooks/
│   └── hooks.json            # Hook → handler mappings
├── scripts/
│   ├── hook-handler.py       # Processes hook events
│   ├── overlay.py            # Persistent overlay window
│   └── generate-placeholders.py
├── themes/
│   └── default/
│       ├── manifest.json
│       ├── characters/       # GIF animations
│       └── sounds/           # Audio files
└── settings-fx.json          # User config
```

## License

MIT
