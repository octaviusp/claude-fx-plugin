---
description: Check Claude FX Plugin requirements
---

# Claude FX Setup

Run the setup checker to verify all dependencies are installed.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/setup.py --force
```

## What It Checks

- **Python 3.9+** - Core runtime
- **Pillow** - Image processing (gradient, resize)
- **pyobjc-framework-Cocoa** - Native macOS UI
- **pyobjc-framework-Quartz** - Window detection

## If Dependencies Are Missing

The script shows:
1. What's missing
2. Copy-paste install commands
3. Instructions to restart Claude Code

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Permission denied | Use `pip3 install --user <package>` |
| Homebrew Python | Add `--break-system-packages` flag |
| SSL errors | Run `pip3 install --trusted-host pypi.org <package>` |
| Command not found | Ensure Python 3.9+ is in PATH |

## After Installing

Restart Claude Code to activate the overlay. The setup check runs automatically on each session start.
