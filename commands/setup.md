---
description: Check and fix Claude FX Plugin requirements
---

# Claude FX Setup

Run the setup checker for Claude FX Plugin to verify all dependencies are installed.

Execute this command to check requirements:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/setup.py --force
```

If dependencies are missing, the setup script will show:
- What's missing (Python, Pillow, tkinter, etc.)
- Platform-specific install commands
- Instructions to restart Claude Code after installing

To automatically install missing dependencies, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/setup.py --force --install
```

After installing dependencies, restart Claude Code to activate the overlay.
