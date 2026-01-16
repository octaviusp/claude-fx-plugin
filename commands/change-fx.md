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
    "maxHeight": 500,
    "bottomGradient": { "enabled": true, "percentage": 0.8 }
  },
  "audio": { "volume": 0.5, "enabled": true },
  "immersion": {
    "breathing": true,
    "sway": true,
    "cursorInfluence": true,
    "transitions": true
  },
  "speechBubble": {
    "enabled": true,
    "backgroundColor": "#1a1a2e",
    "borderColor": "#4a9eff",
    "fontColor": "#ffffff"
  },
  "emotionOverlays": { "enabled": true },
  "aura": {
    "enabled": true,
    "color": "#6699ff",
    "opacity": 0.5,
    "minRadius": 8,
    "maxRadius": 14
  }
}
```

**Key Settings:**
- **Aura:** Pulsing glow effect (color, opacity, radius)
- **Speech Bubbles:** Styled bubbles (backgroundColor, borderColor, fontColor)
- **Immersion:** Breathing, sway, cursor tracking animations
- **Bottom Gradient:** Fades the bottom of the image (default 80%)
- **Emotion Overlays:** Sparkles, sweat drops, zzz effects

Changes take effect on next Claude Code session.
