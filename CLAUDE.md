# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

claude-fx-plugin is a Claude Code plugin that displays a persistent animated mascot overlay beside your terminal. The overlay reacts to Claude's activity in real-time - showing different states for greeting, working, success, error, and celebration.

**Key Features**:
- True transparency using PyObjC native macOS NSWindow
- **Immersion system** - breathing, sway, cursor tracking, transition animations
- **Speech bubbles** - customizable styled messages per state
- **Emotion overlays** - programmatic effects (sparkles, sweat drops, zzz)
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
3. **overlay.py** receives state updates via socket, displays transparent PNG overlay with immersion effects

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
├── messages.json             # Speech bubble messages per state
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
- **Immersion system** - breathing, sway, cursor influence, transitions
- **Speech bubbles** - customizable styled messages
- **Emotion overlays** - programmatic visual effects
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
  "theme": "default",
  "immersion": {
    "breathing": true,
    "sway": true,
    "cursorInfluence": true,
    "cursorInfluenceStrength": 0.5,
    "transitions": true
  },
  "speechBubble": {
    "enabled": true,
    "backgroundColor": "#1a1a2e",
    "borderColor": "#4a9eff",
    "borderWidth": 2,
    "borderRadius": 8,
    "fontFamily": "SF Mono",
    "fontSize": 13,
    "fontColor": "#ffffff",
    "padding": 10,
    "displayDuration": 3.0
  },
  "emotionOverlays": {
    "enabled": true
  }
}
```

### Settings Reference

#### Overlay Settings
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

#### Audio Settings
| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `audio.enabled` | bool | true | Enable sound effects |
| `audio.volume` | float | 0.5 | Volume level (0.0-1.0) |

#### Immersion Settings
| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `immersion.breathing` | bool | true | Subtle scale pulse animation |
| `immersion.sway` | bool | true | Gentle rotation and drift |
| `immersion.cursorInfluence` | bool | true | Character tilts toward cursor |
| `immersion.cursorInfluenceStrength` | float | 0.5 | How much cursor affects tilt (0.0-1.0) |
| `immersion.transitions` | bool | true | State change animations |

#### Speech Bubble Settings
| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `speechBubble.enabled` | bool | true | Show speech bubbles |
| `speechBubble.backgroundColor` | string | "#1a1a2e" | Bubble background color |
| `speechBubble.borderColor` | string | "#4a9eff" | Bubble border color |
| `speechBubble.borderWidth` | int | 2 | Border thickness in pixels |
| `speechBubble.borderRadius` | int | 8 | Corner radius in pixels |
| `speechBubble.fontFamily` | string | "SF Mono" | Font family name |
| `speechBubble.fontSize` | int | 13 | Font size in points |
| `speechBubble.fontColor` | string | "#ffffff" | Text color |
| `speechBubble.padding` | int | 10 | Inner padding in pixels |
| `speechBubble.displayDuration` | float | 3.0 | Seconds to show bubble |

#### Emotion Overlay Settings
| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `emotionOverlays.enabled` | bool | true | Show emotion effects |

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

### Breathing Effect
```python
BREATH_INTENSITY = 0.008  # 0.8% scale change
BREATH_PERIOD = 3.5       # seconds for full breath cycle
```

### Sway Effect
```python
SWAY_ANGLE = 1.5    # degrees max rotation
SWAY_PERIOD = 4.0   # seconds for full sway cycle
SWAY_X = 2.0        # pixels horizontal drift
```

### Cursor Influence
```python
CURSOR_TILT_MAX = 3.0    # degrees max tilt toward cursor
CURSOR_SHIFT_MAX = 5.0   # pixels max shift toward cursor
CURSOR_FALLOFF = 300.0   # distance for effect falloff
```

### Aura Glow
```python
AURA_COLOR = (0.4, 0.55, 1.0, 1.0)  # Soft blue (R, G, B, A)
AURA_MIN_RADIUS = 8.0
AURA_MAX_RADIUS = 14.0
AURA_PERIOD = 1.8       # seconds for pulse cycle
AURA_OPACITY = 0.5
```

### State Transitions
| State | Animation | Parameters |
|-------|-----------|------------|
| greeting | scale_pop | scale: 1.08, duration: 0.25s |
| working | scale_pop | scale: 1.05, duration: 0.2s |
| success | bounce | height: 15px, duration: 0.4s |
| error | shake | intensity: 8px, cycles: 3, duration: 0.3s |
| celebrating | bounce | height: 20px, duration: 0.5s |
| farewell | scale_pop | scale: 1.05, duration: 0.2s |

### Emotion Overlays
| State | Overlays | Description |
|-------|----------|-------------|
| error | sweat_drop | Animated falling drop |
| success | sparkle | Pulsing sparkles |
| celebrating | sparkle, star | Sparkles + rotating star |
| sleeping | zzz | Floating Z letters |
| working | focus_lines | Radiating concentration lines |

### Bottom Gradient
Applied via PIL before display. Multiplies alpha channel by a gradient that goes from 1.0 (full opacity) at `start_y` to 0.0 (transparent) at the bottom.

## Speech Bubble System

### messages.json
```json
{
  "greeting": ["Ready when you are.", "Let's build something."],
  "working": ["On it...", "Processing..."],
  "success": ["Done.", "Got it.", "Clean."],
  "error": ["Hmm, let me check.", "Something's off."],
  "celebrating": ["Nice work!", "Victory!"],
  "sleeping": ["Zzz...", "*yawn*"],
  "farewell": ["See you!", "Bye for now."],
  "idle": ["Need anything?", "I'm here."]
}
```

Messages are randomly selected per state. Users can customize by editing `messages.json`.

## Multi-Instance Architecture

Each terminal window gets its own overlay instance:

1. **Session ID** = Shell PID (unique per terminal window, even in same terminal app)
2. **Socket path** = `~/.claude-fx/sock-{SHELL_PID}.sock`
3. **PID file** = `~/.claude-fx/pid-{SHELL_PID}.txt`

This allows multiple Claude Code sessions to run simultaneously with independent overlays.

## Dependencies

Required (auto-detected by setup.py):
- **Python 3.9+** - Core runtime
- **Pillow** - Image processing (gradient, resize, shadow)
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
- **No special assets needed** - immersion effects work on ANY static PNG

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

## Recent Changes (v2.0.0)

### Immersion System
- **Breathing animation** - Subtle Y-axis scale pulse (0.8% intensity, 3.5s cycle)
- **Sway animation** - Gentle rotation (±1.5°) and horizontal drift (±2px)
- **Cursor influence** - Character tilts toward mouse cursor with distance falloff
- **State transitions** - Bounce, shake, and scale pop animations on state change

### Speech Bubbles
- **Squared rectangles** with user-defined styling
- Configurable background, border, font, colors, radius
- Random message selection from pool per state
- Auto-fade after configurable duration
- Messages customizable via `messages.json`

### Emotion Overlays
- **Programmatically drawn** - works on ANY static PNG
- sweat_drop (error), sparkles (success), zzz (sleeping), focus_lines (working)
- Animated effects with phase-based motion

### Previous (v1.0.0)
- Multi-instance support via shell PID isolation
- Bottom gradient fade for text readability
- Floating animation with glowing aura
- Unix Socket IPC for zero-latency updates
- Responsive sizing with terminal height
- Sound system with multi-format support
