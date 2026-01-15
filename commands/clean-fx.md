---
description: Kill all overlay processes and clean up state files
---

# Clean FX

Emergency cleanup command to kill all stuck overlay processes and remove state files.

## Run This Command

```bash
pkill -9 -f 'python3.*overlay.py' 2>/dev/null; rm -f ~/.claude-fx/sock-*.sock ~/.claude-fx/pid-*.txt 2>/dev/null; echo "All FX overlays killed and state cleaned"
```

## What It Does

- Force kills ALL overlay.py processes (all terminals)
- Removes all Unix socket files
- Removes all PID files

## When to Use

| Scenario | Solution |
|----------|----------|
| Overlay stuck on screen | Run this command, restart session |
| Multiple overlays visible | Run this command, restart session |
| Overlay not responding | Run this command, restart session |
| Wrong overlay position | Run this command, restart session |

## After Cleanup

Start a new Claude Code session to get a fresh overlay. The setup check will run automatically.
