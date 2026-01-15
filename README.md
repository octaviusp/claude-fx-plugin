# Claude FX Plugin

Animated mascot companion for Claude Code. A transparent overlay that floats beside your terminal and reacts to Claude's activity in real-time.

![Mascot](themes/default/characters/greeting.png)

## Installation

**Inside Claude Code, run:**

```
/plugin marketplace add octaviusp/claude-fx-plugin
/plugin install claude-fx-plugin@claude-fx-marketplace
```

Done! The mascot will appear on your next session.

### Alternative: Manual Install

```bash
git clone https://github.com/octaviusp/claude-fx-plugin
claude --plugin-dir ./claude-fx-plugin
```

On first run, install dependencies when prompted.

## Features

- **Reactive States** - 8 character states (idle, greeting, working, success, error, celebrating, sleeping, farewell)
- **Floating Animation** - Subtle bobbing motion with glowing aura effect
- **Sound Effects** - Audio feedback for each state
- **Bottom Gradient Fade** - Character fades at bottom for text readability
- **Responsive Sizing** - Scales with terminal height
- **Multi-Instance Support** - Multiple terminals simultaneously
- **Smart Visibility** - Only shows when its terminal is focused

## Configuration

Edit `settings-fx.json` in the plugin folder:

```json
{
  "overlay": {
    "enabled": true,
    "responsive": true,
    "heightRatio": 1,
    "maxHeight": 750,
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

### Settings Reference

| Setting | Description | Default |
|---------|-------------|---------|
| `overlay.enabled` | Show/hide the overlay | `true` |
| `overlay.responsive` | Scale with terminal height | `true` |
| `overlay.heightRatio` | Ratio of terminal height to use (0.0-1.0) | `1` |
| `overlay.maxHeight` | Maximum image height in pixels | `750` |
| `overlay.customX/Y` | Fixed position coordinates | `null` |
| `overlay.offsetX/Y` | Offset from terminal edge | `20`/`0` |
| `overlay.showOnlyWhenTerminalActive` | Hide when terminal loses focus | `true` |
| `overlay.fadeAnimation` | Smooth show/hide transitions | `true` |
| `overlay.bottomGradient.enabled` | Fade bottom of image | `true` |
| `overlay.bottomGradient.percentage` | Portion to fade (0.0-1.0) | `0.8` |
| `audio.enabled` | Enable sound effects | `true` |
| `audio.volume` | Volume level (0.0-1.0) | `0.5` |
| `theme` | Theme folder name | `"default"` |

## Customization

### Custom Characters

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

**Requirements:** PNG with transparent background (any size, auto-scaled)

### Custom Sounds

Drop audio files in `themes/default/sounds/`:

```
greeting.aiff    # Session start
working.aiff     # Tool execution
success.aiff     # Task completed
error.aiff       # Something failed
celebrating.aiff # Response finished
farewell.aiff    # Session end
```

**Supported formats:** `.wav`, `.mp3`, `.aiff`, `.m4a`, `.caf`, `.aac`

## Commands

The plugin adds slash commands to Claude Code:

| Command | Description |
|---------|-------------|
| `/claude-fx:setup` | Check and install dependencies |
| `/claude-fx:change-fx` | Guide to customize characters and sounds |
| `/claude-fx:clean-fx` | Emergency cleanup (kill stuck overlays) |

## Requirements

**macOS only** - Uses PyObjC for native transparent windows

Dependencies (auto-checked on startup):
- Python 3.9+
- Pillow (image processing)
- pyobjc-framework-Cocoa (native UI)
- pyobjc-framework-Quartz (window detection)

Manual check:
```bash
python3 scripts/setup.py --force
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Overlay not showing | Run `/claude-fx:setup` to check dependencies |
| Wrong position | Set `customX`/`customY` in settings, or adjust `offsetX`/`offsetY` |
| No sound | Check `audio.enabled: true` and `audio.volume > 0` |
| Overlay stuck | Run `/claude-fx:clean-fx` to force cleanup |
| Multiple overlays | Run `/claude-fx:clean-fx` then restart session |
| Text hard to read | Increase `bottomGradient.percentage` (e.g., `0.9`) |

## Project Structure

```
claude-fx-plugin/
├── .claude-plugin/
│   └── plugin.json       # Plugin manifest
├── hooks/
│   └── hooks.json        # Hook event mappings
├── scripts/
│   ├── hook-handler.py   # Processes hooks, plays sounds
│   ├── overlay.py        # PyObjC transparent overlay
│   └── setup.py          # Dependency checker
├── themes/default/
│   ├── characters/       # PNG images per state
│   ├── sounds/           # Audio files
│   └── manifest.json     # State → asset mappings
├── commands/             # Slash command documentation
├── settings-fx.json      # User configuration
└── README.md
```

## Platform Support

| Platform | Status |
|----------|--------|
| macOS | Full support |
| Linux | Not supported |
| Windows | Not supported |

## License

MIT - See [LICENSE](LICENSE) for details.

## Author

[Octavio](https://github.com/octaviusp)
