# claude-fx-plugin

Visual and audio feedback for Claude Code hooks.

claude-fx-plugin is a companion addon for Claude Code that brings your coding sessions to life. It displays animated visuals (GIFs, images, sprites) and plays sound effects in response to Claude Code's activity — when it's thinking, writing code, executing commands, or completing tasks.

## How It Works

claude-fx-plugin integrates with Claude Code's native hooks system. Hooks are event triggers that fire at specific moments during Claude's workflow:

- **PreToolUse** — Before Claude executes a tool (Write, Edit, Bash, etc.)
- **PostToolUse** — After Claude completes a tool execution
- **Notification** — When Claude sends status updates
- **Stop** — When Claude finishes a task

When these events fire, claude-fx-plugin triggers visual overlays and audio effects based on your configured theme.

## Installation

### Via Plugin Command

```bash
# In Claude Code
/plugin install claude-fx-plugin
```

### Manual Installation

1. Clone this repository to your plugins directory:
   ```bash
   git clone https://github.com/YOUR_USERNAME/claude-fx-plugin ~/.claude/plugins/claude-fx-plugin
   ```

2. Install dependencies:
   ```bash
   cd ~/.claude/plugins/claude-fx-plugin
   npm install
   ```

3. Enable the plugin in Claude Code:
   ```bash
   /plugin enable claude-fx-plugin
   ```

## Configuration

Edit `config.json` in the plugin root:

```json
{
  "theme": "default",
  "volume": 0.5,
  "overlay": {
    "enabled": true,
    "position": "bottom-right",
    "size": 200,
    "duration": 2000
  },
  "audio": {
    "enabled": true
  }
}
```

## Creating Custom Themes

Themes live in the `themes/` directory. Each theme contains:

```
themes/my-theme/
├── manifest.json          # Effect mappings
├── animations/            # GIF/image files
│   ├── working.gif
│   ├── writing.gif
│   └── ...
└── sounds/                # Audio files (WAV/MP3/OGG)
    ├── start.wav
    ├── complete.wav
    └── ...
```

### Theme Manifest Format

```json
{
  "name": "my-theme",
  "description": "My custom theme",
  "version": "1.0.0",
  "effects": {
    "PreToolUse": {
      "message": "Working...",
      "sound": "start.wav",
      "animation": "working.gif"
    },
    "PreToolUse:Write": {
      "message": "Writing file...",
      "sound": "write.wav",
      "animation": "writing.gif"
    },
    "PostToolUse": {
      "message": "Done!",
      "sound": "complete.wav",
      "animation": "done.gif"
    },
    "Stop": {
      "message": "Task complete!",
      "sound": "finish.wav",
      "animation": "finish.gif"
    }
  }
}
```

Effects can be mapped to:
- General events: `PreToolUse`, `PostToolUse`, `Stop`, `Notification`
- Tool-specific events: `PreToolUse:Write`, `PreToolUse:Bash`, `PostToolUse:Edit`, etc.

## Features

- **Animated Overlays** — Display GIFs, images, or sprite animations
- **Sound Effects** — Play audio cues synced to Claude's actions
- **Theme Packs** — Swap between different visual/audio themes
- **Lightweight** — Minimal resource footprint, runs in background
- **Event-Driven** — Reacts only when Claude is active
- **Customizable** — Create and import your own asset packs

## Platform Support

- **macOS**: Uses `afplay` for audio, AppleScript for notifications
- **Linux**: Uses `paplay` for audio, `notify-send` for notifications
- **Windows**: Uses PowerShell for audio

## License

MIT
