# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

claude-fx-plugin is a Claude Code plugin that provides visual and audio feedback in response to Claude's activity. It hooks into Claude Code's event system to play sounds and show notifications when Claude executes tools, completes tasks, or sends notifications.

## Directory Structure

```
claude-fx-plugin/
├── .claude-plugin/
│   └── plugin.json           # REQUIRED: Plugin manifest for Claude Code
├── hooks/
│   └── hooks.json            # REQUIRED: Maps events to handler commands
├── scripts/
│   └── fx-handler.js         # Main handler script (entry point)
├── themes/
│   └── <theme-name>/
│       ├── manifest.json     # Effect mappings for this theme
│       ├── sounds/           # Audio files (WAV, MP3, OGG)
│       └── animations/       # Image files (GIF, PNG) - future use
├── tests/
│   └── fx-handler.test.js    # Unit tests
├── config.json               # User preferences (theme, volume, etc.)
├── package.json              # Node.js dependencies
└── README.md
```

## File Purposes

### `.claude-plugin/plugin.json` (Required)
Plugin manifest that registers this as a Claude Code plugin. Must contain:
- `name`: Plugin identifier
- `description`: What the plugin does
- `hooks`: Path to hooks configuration (relative: `"hooks/hooks.json"`)

### `hooks/hooks.json` (Required)
Maps Claude Code events to handler commands. Structure:
```json
{
  "hooks": {
    "EventName": [{
      "matcher": "*",           // Tool pattern (* = all, "Write" = specific)
      "hooks": [{
        "type": "command",
        "command": "node ${CLAUDE_PLUGIN_ROOT}/scripts/fx-handler.js",
        "timeout": 5000
      }]
    }]
  }
}
```
- Use `${CLAUDE_PLUGIN_ROOT}` for portable paths
- `matcher` only applies to PreToolUse/PostToolUse (tool name matching)
- `timeout` in milliseconds (default 60000)

### `scripts/fx-handler.js` (Entry Point)
Node.js script that:
1. Reads JSON from stdin (hook event data)
2. Loads `config.json` for user preferences
3. Loads theme `manifest.json` for effect mappings
4. Plays audio via system commands (`afplay`/`paplay`/PowerShell)
5. Shows notification via system commands (`osascript`/`notify-send`)
6. Always exits with code 0 (never blocks Claude)

### `config.json` (User Config)
```json
{
  "theme": "default",        // Theme folder name in themes/
  "volume": 0.5,             // 0.0 to 1.0
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

### `themes/<name>/manifest.json` (Theme Config)
Maps events to effects. Keys can be:
- Event only: `"PreToolUse"`, `"PostToolUse"`, `"Stop"`, `"Notification"`
- Event + Tool: `"PreToolUse:Write"`, `"PreToolUse:Bash"`, `"PostToolUse:Edit"`

Tool-specific mappings take precedence over general event mappings.

```json
{
  "name": "theme-name",
  "effects": {
    "PreToolUse": {
      "sound": "start.wav",
      "animation": "working.gif",
      "message": "Working..."
    },
    "PreToolUse:Write": {
      "sound": "write.wav",
      "message": "Writing file..."
    }
  }
}
```

## Claude Code Hook Events

| Event | When Fired | Has Matcher | Stdin Contains |
|-------|------------|-------------|----------------|
| `PreToolUse` | Before tool executes | Yes | `tool_name`, `tool_input` |
| `PostToolUse` | After tool completes | Yes | `tool_name`, `tool_input`, `tool_result` |
| `Stop` | Agent finishes responding | No | `session_id` |
| `Notification` | System notification | No | notification data |
| `SubagentStop` | Subagent finishes | No | `subagent_name` |
| `SessionStart` | Session begins | No | `session_id` |
| `SessionEnd` | Session ends | No | `session_id` |

### Stdin JSON Format
```json
{
  "session_id": "abc123",
  "hook_event_name": "PreToolUse",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/path/to/file.js",
    "content": "..."
  },
  "cwd": "/project/dir",
  "transcript_path": "/path/to/transcript"
}
```

### Exit Codes
- `0`: Success (continue normally)
- `2`: Block operation (stderr shown to Claude)
- Other: Non-blocking error

## Commands

```bash
npm install                              # Install dependencies
npm test                                 # Run all tests
npm test -- tests/fx-handler.test.js    # Run single test
npm run lint                            # ESLint
```

## Environment Variables (Set by Claude Code)

| Variable | Description |
|----------|-------------|
| `CLAUDE_PLUGIN_ROOT` | Absolute path to plugin directory |
| `CLAUDE_PROJECT_DIR` | Project being worked on |
| `CLAUDE_CODE_REMOTE` | "true" if running in web/remote mode |

## Adding Sound Effects

1. Place audio files in `themes/<theme>/sounds/`
2. Reference filename in theme manifest under `effects.<Event>.sound`
3. Supported formats: WAV (recommended), MP3, OGG

## Creating a New Theme

1. Create folder: `themes/my-theme/`
2. Create `manifest.json` with effect mappings
3. Add `sounds/` folder with audio files
4. Add `animations/` folder with images (optional, for future overlay)
5. Update `config.json`: `"theme": "my-theme"`

## Platform Audio Commands

| Platform | Command | Volume Format |
|----------|---------|---------------|
| macOS | `afplay -v 0.5 file.wav` | 0.0-1.0 float |
| Linux | `paplay --volume 32768 file.wav` | 0-65536 int |
| Windows | PowerShell `SoundPlayer` | N/A |

## Platform Notification Commands

| Platform | Command |
|----------|---------|
| macOS | `osascript -e 'display notification "msg" with title "Claude FX"'` |
| Linux | `notify-send "Claude FX" "msg"` |
| Windows | Not implemented yet |

## Key Implementation Details

- Handler runs detached (`spawn` with `detached: true, stdio: 'ignore'`)
- Audio/notifications don't block the handler exit
- Invalid JSON input silently exits with code 0
- Missing theme silently exits with code 0
- Missing effect for event silently exits with code 0
