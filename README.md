# Claude FX Plugin

Animated mascot companion for Claude Code. Reacts to Claude's activity in real-time with character animations and sound effects.

![Mascot](themes/default/characters/greeting.png)

## Quick Start

```bash
# 1. Clone
git clone https://github.com/octaviusp/claude-fx-plugin

# 2. Run Claude Code with plugin
claude --plugin-dir ./claude-fx-plugin

# 3. Install dependencies when prompted
```

On first run, you'll see required dependencies. Install them and restart Claude Code.

## Configuration

Edit `settings-fx.json`:

```json
{
  "overlay": {
    "enabled": true,
    "maxHeight": 350,
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

| Setting | Description | Default |
|---------|-------------|---------|
| `overlay.enabled` | Show/hide overlay | true |
| `overlay.maxHeight` | Image height in pixels | 350 |
| `overlay.offsetX/Y` | Position offset from terminal | 20/40 |
| `overlay.responsive` | Scale with terminal height | true |
| `audio.enabled` | Enable sound effects | true |
| `audio.volume` | Volume (0.0 - 1.0) | 0.5 |
| `theme` | Theme folder name | default |

## Custom Characters

Drop PNG files in `themes/default/characters/`:

```
idle.png        # Default state
greeting.png    # Session start
working.png     # Tool execution
success.png     # Task completed
error.png       # Something failed
celebrating.png # Response finished
sleeping.png    # Extended idle
```

**Requirements:** PNG with transparent background, any size (auto-scaled)

## Custom Sounds

Drop audio files in `themes/default/sounds/`:

```
greeting.aiff   # Session start
working.aiff    # Tool execution
success.aiff    # Task completed
error.aiff      # Something failed
celebrating.aiff # Response finished
farewell.aiff   # Session end
```

**Formats:** `.wav`, `.mp3`, `.aiff`, `.m4a`, `.caf`, `.aac`

## Requirements

**macOS only** (uses PyObjC for native transparency)

Check/install dependencies:
```bash
python3 scripts/setup.py --force
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Overlay not showing | Run `python3 scripts/setup.py --force` |
| Wrong position | Set `customX`/`customY` in settings |
| No sound | Check `audio.enabled` and `audio.volume` |
| Overlay on wrong terminal | Restart Claude Code in desired terminal |

## Project Structure

```
claude-fx-plugin/
├── scripts/
│   ├── hook-handler.py   # Hook processor + sounds
│   ├── overlay.py        # PyObjC overlay window
│   └── setup.py          # Dependency checker
├── themes/default/
│   ├── characters/       # PNG images
│   ├── sounds/           # Audio files
│   └── manifest.json     # State mappings
└── settings-fx.json      # User config
```

## License

MIT
