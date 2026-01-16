---
description: Switch character images folder permanently
---

# Change Character

Switch to a different character folder. Changes persist across sessions.

## Usage

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/hook-handler.py change-character characters2
```

## Available Folders

Check `themes/default/` in the plugin folder:
- `characters` - Default character
- `characters2` - Alternate character
- `character3` - Latest character

## Notes

- Changes apply immediately and persist across sessions
- Sounds stay the same
- Missing images fall back to default
- Saved to `settings-fx.json` under `characterFolder`
