# Claude FX Plugin

A persistent animated mascot companion for Claude Code. Your waifu lives beside your terminal and reacts to Claude's activity in real-time!

![Waifu Mascot](themes/default/characters/greeting.png)

## Features

- **True Transparency** - Character floats with no background window (PyObjC native macOS)
- **State-Based Animations** - Different poses for idle, working, success, error, celebrating
- **Sound Effects** - Audio feedback with configurable volume
- **Terminal-Aware** - Auto-positions next to your terminal window
- **Easy Customization** - Drop in your own PNG/GIF mascots
- **Auto Setup** - Detects and helps install missing dependencies

## Quick Start

### 1. Clone the plugin

```bash
git clone https://github.com/octaviusp/claude-fx-plugin
```

### 2. Run Claude Code with the plugin

```bash
claude --plugin-dir ./claude-fx-plugin
```

### 3. Follow the setup prompts

On first run, the plugin checks dependencies and shows install commands if needed:

```
=======================================================
  Claude FX Plugin - Setup Check
=======================================================

  Requirements:

  ✓ Platform (macos/arm64)
  ✓ Python 3.9+ (3.14.2)
  ✗ Pillow (not installed)
  ✗ Quartz (not installed)

  To fix, run these commands:

    $ pip3 install pillow --break-system-packages
    $ pip3 install pyobjc-framework-Quartz --break-system-packages

  After installing, restart Claude Code to activate the plugin.
```

## How It Works

```
Claude Code Hook → hook-handler.py → state.json → overlay.py
                         ↓
                   Transparent NSWindow with mascot
```

1. Claude Code fires hooks (SessionStart, PreToolUse, PostToolUse, Stop)
2. `hook-handler.py` maps events to states and writes `~/.claude-fx/state.json`
3. `overlay.py` polls the state file and updates the displayed character
4. The mascot floats beside your terminal with true transparency

## States

| State | Trigger | Animation |
|-------|---------|-----------|
| `idle` | Default | Relaxed pose |
| `greeting` | SessionStart | Waving hello |
| `working` | PreToolUse | Focused/busy |
| `success` | PostToolUse (ok) | Thumbs up |
| `error` | PostToolUse (fail) | Worried expression |
| `celebrating` | Stop | Victory pose |
| `sleeping` | Extended idle | Zzz animation |

## Configuration

Edit `settings-fx.json` to customize:

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

### Settings Explained

| Setting | Description | Default |
|---------|-------------|---------|
| `maxHeight` | Maximum image height in pixels | 350 |
| `position` | `"auto"` for terminal detection | auto |
| `customX/Y` | Fixed position (set both or use auto) | null |
| `offsetX/Y` | Offset from terminal edge | 20/40 |
| `volume` | Sound volume (0.0 to 1.0) | 0.5 |
| `theme` | Theme folder name | default |

## Custom Characters

Replace images in `themes/default/characters/`:

```
themes/default/characters/
├── idle.png        # Default state
├── greeting.png    # Session start
├── working.png     # Tool execution
├── success.png     # Task completed
├── error.png       # Something failed
├── celebrating.png # Response finished
└── sleeping.png    # Extended idle
```

### Image Requirements

- **PNG with transparent background** (recommended)
- **GIF supported** for animations
- Any size (auto-scaled to `maxHeight`)
- RGBA color mode for transparency

## Manual Commands

```bash
# Run setup check
python3 scripts/setup.py --force

# Auto-install dependencies
python3 scripts/setup.py --force --install

# Start overlay manually
CLAUDE_FX_ROOT="$(pwd)" python3 scripts/overlay.py &

# Test state changes
echo '{"state": "greeting"}' > ~/.claude-fx/state.json
echo '{"state": "working"}' > ~/.claude-fx/state.json
echo '{"state": "success"}' > ~/.claude-fx/state.json

# Stop overlay
pkill -f overlay.py

# Reset setup (re-check dependencies)
rm ~/.claude-fx/setup_ok
```

## Dependencies

Auto-detected and installed by setup system:

| Dependency | Purpose | Install |
|------------|---------|---------|
| Python 3.9+ | Runtime | Pre-installed on macOS |
| Pillow | Image processing | `pip3 install pillow` |
| pyobjc-framework-Quartz | Terminal detection | `pip3 install pyobjc-framework-Quartz` |
| pyobjc-framework-Cocoa | Native UI | Included with Quartz |

## Project Structure

```
claude-fx-plugin/
├── .claude-plugin/
│   └── plugin.json           # Plugin manifest
├── hooks/
│   └── hooks.json            # Hook → handler mappings
├── scripts/
│   ├── hook-handler.py       # Processes hook events
│   ├── overlay.py            # PyObjC transparent overlay
│   └── setup.py              # Dependency checker
├── commands/
│   └── setup.md              # /claude-fx:setup command
├── themes/
│   └── default/
│       ├── manifest.json     # State → asset mappings
│       ├── characters/       # PNG/GIF images
│       └── sounds/           # WAV audio files
├── settings-fx.json          # User configuration
├── CLAUDE.md                 # Claude Code guidance
└── README.md
```

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| **macOS** | Full Support | PyObjC + Quartz for transparency |
| Linux | Planned | Needs GTK/Qt implementation |
| Windows | Not Supported | - |

## Creating Custom Themes

1. Create a new folder in `themes/`:
   ```bash
   mkdir themes/my-theme
   ```

2. Add `manifest.json`:
   ```json
   {
     "name": "my-theme",
     "version": "1.0.0",
     "states": {
       "idle": { "animation": "characters/idle.png" },
       "greeting": { "animation": "characters/greeting.png" },
       "working": { "animation": "characters/working.png" },
       "success": { "animation": "characters/success.png" },
       "error": { "animation": "characters/error.png" },
       "celebrating": { "animation": "characters/celebrating.png" },
       "sleeping": { "animation": "characters/sleeping.png" }
     }
   }
   ```

3. Add your images to `characters/` and sounds to `sounds/`

4. Update `settings-fx.json`:
   ```json
   { "theme": "my-theme" }
   ```

## Troubleshooting

### Overlay not showing
```bash
# Check if setup completed
cat ~/.claude-fx/setup_ok

# Re-run setup
python3 scripts/setup.py --force

# Check for running overlay
ps aux | grep overlay.py
```

### Wrong position
- Set custom position in `settings-fx.json`:
  ```json
  { "overlay": { "customX": 1200, "customY": 100 } }
  ```

### No sound
- Check `audio.enabled` and `audio.volume` in settings
- Verify WAV files exist in `themes/default/sounds/`

## License

MIT

## Credits

- Waifu mascot character - AI Generated
- Built with PyObjC for native macOS transparency
- Powered by Claude Code hooks system
