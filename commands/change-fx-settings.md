---
description: Customize overlay settings with natural language
argument-hint: describe your changes
---

# Change FX Settings

Customize overlay appearance, position, animations, and behavior using natural language.

## Usage

Describe what you want to change after the command:

```
/claude-fx:change-fx-settings make it bigger and move to bottom right
/claude-fx:change-fx-settings disable animations and reduce opacity
/claude-fx:change-fx-settings position at X:100 Y:200, max height 600
/claude-fx:change-fx-settings enable gradient, increase volume to 80%
```

## What You Can Customize

**Size & Position:**
- Height/width (heightRatio, maxHeight)
- Position (customX, customY, offsetX, offsetY)
- Responsive sizing (responsive)

**Visual Effects:**
- Bottom gradient (bottomGradient.enabled, percentage)
- Fade animations (fadeAnimation)
- Immersion effects (breathing, sway, cursorInfluence)
- Emotion overlays (emotionOverlays.enabled)

**Behavior:**
- Show only when terminal active (showOnlyWhenTerminalActive)
- Audio (audio.enabled, volume)

**Speech Bubbles:**
- Enable/disable (speechBubble.enabled)
- Colors (backgroundColor, borderColor, fontColor)
- Font (fontFamily, fontSize)
- Display duration

## Examples

**Make it smaller and move right:**
```
/claude-fx:change-fx-settings reduce height to 500px, move 100px right
```

**Disable all animations:**
```
/claude-fx:change-fx-settings turn off breathing, sway, and transitions
```

**Custom position:**
```
/claude-fx:change-fx-settings position at X:1500 Y:100
```

**Adjust audio:**
```
/claude-fx:change-fx-settings set volume to 70% and enable audio
```

## How It Works

1. Run the command with your description
2. Claude interprets your request
3. Updates `settings-fx.json`
4. Reloads settings in active overlay
5. Changes apply immediately

## Notes

- Changes are permanent (saved to settings-fx.json)
- Use natural language - Claude understands various phrasings
- Check current settings: `cat settings-fx.json`
- Restart overlay if reload doesn't work
