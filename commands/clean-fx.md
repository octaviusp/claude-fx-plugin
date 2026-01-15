---
description: Kill all overlay processes and clean up state files
---

# Clean FX

Emergency cleanup command to kill all stuck overlay processes and remove state files.

Run this command:

```bash
pkill -9 -f overlay.py 2>/dev/null; rm -f ~/.claude-fx/*.pid ~/.claude-fx/*.lock ~/.claude-fx/state*.json 2>/dev/null; echo "All FX overlays killed and state cleaned"
```

This will:
- Force kill ALL overlay.py processes (all terminals)
- Remove all PID files
- Remove all lock files
- Remove all state files

Use when overlays get stuck or duplicate.
