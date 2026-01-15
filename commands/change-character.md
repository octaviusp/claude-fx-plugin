---
description: Switch character images folder for this session
---

# Change Character

Switch to a different character folder. Session-only, doesn't persist.

## Usage

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/hook-handler.py change-character characters2
```

## Available Folders

Check `themes/default/` in the plugin folder:
- `characters` - Default character
- `characters2` - Alternate character

## Notes

- Changes apply immediately
- Sounds stay the same
- Missing images fall back to default
- Resets when session ends
