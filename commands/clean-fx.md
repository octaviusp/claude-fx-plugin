---
description: Kill all overlay processes and clean up state files
---

# Clean FX

Emergency cleanup command to kill all stuck overlay processes, orphaned sounds, and remove state files.

## Run This Command

```bash
pkill -9 -f 'python3.*overlay.py' 2>/dev/null
pkill -9 -f 'afplay.*claude-fx' 2>/dev/null
rm -f ~/.claude-fx/sock-*.sock ~/.claude-fx/pid-*.txt ~/.claude-fx/overlay.sock 2>/dev/null
echo "Cleaned: overlays, sounds, sockets, and PID files"
```

## What It Does

- Force kills ALL overlay.py processes (all terminals)
- Force kills ALL orphaned afplay sound processes from claude-fx
- Removes all Unix socket files (including legacy overlay.sock)
- Removes all PID files

## When to Use

| Scenario | Solution |
|----------|----------|
| Overlay stuck on screen | Run this command, restart session |
| Multiple overlays visible | Run this command, restart session |
| Overlay not responding | Run this command, restart session |
| Sounds keep playing after exit | Run this command |
| PC feels slow from orphaned processes | Run this command |

## If coreaudiod is using high memory

If Activity Monitor shows `coreaudiod` using excessive memory (>500MB), restart it:

```bash
sudo killall coreaudiod
```

macOS will auto-restart it with fresh memory. Audio will briefly cut out then resume.

## After Cleanup

Start a new Claude Code session to get a fresh overlay. The setup check will run automatically.
