---
description: Check Claude FX Plugin requirements
---

# Claude FX Setup

Run the setup checker to verify all dependencies are installed.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/setup.py --force
```

If dependencies are missing, the script shows:
- What's missing (Pillow, pyobjc-framework-Quartz)
- Copy-paste install commands
- Instructions to restart Claude Code

After installing, restart Claude Code to activate the overlay.
