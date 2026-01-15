---
description: How to customize character images and sounds
---

# Customize Claude FX

## Change Character Images

Drop PNG files in `themes/default/characters/`:

```
idle.png        → Default state
greeting.png    → Session start
working.png     → Tool execution
success.png     → Task completed
error.png       → Something failed
celebrating.png → Response finished
sleeping.png    → Extended idle
```

**Requirements:** PNG with transparent background (any size, auto-scaled)

## Change Sounds

Drop audio files in `themes/default/sounds/`:

```
greeting.aiff   → Session start
working.aiff    → Tool execution
success.aiff    → Task completed
error.aiff      → Something failed
celebrating.aiff → Response finished
farewell.aiff   → Session end
```

**Formats:** `.wav`, `.mp3`, `.aiff`, `.m4a`, `.caf`, `.aac`

## Settings

Edit `settings-fx.json` in the plugin folder:

```json
{
  "overlay": {
    "maxHeight": 350,
    "bottomGradient": { "enabled": true, "percentage": 0.2 }
  },
  "audio": { "volume": 0.5, "enabled": true }
}
```

**Bottom Gradient:** Fades the bottom 20% of the image to transparent so you can read text behind it. Adjust `percentage` (0.0-1.0) or set `enabled: false` to disable.

Changes take effect on next Claude Code session.
