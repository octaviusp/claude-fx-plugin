#!/usr/bin/env python3
"""
Claude FX Hook Handler - Receives hook events and updates overlay state.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Paths
HOME = Path.home()
FX_DIR = HOME / '.claude-fx'
STATE_FILE = FX_DIR / 'state.json'
PID_FILE = FX_DIR / 'overlay.pid'

PLUGIN_ROOT = Path(os.environ.get(
    'CLAUDE_PLUGIN_ROOT',
    Path(__file__).parent.parent
))


def read_stdin() -> dict:
    """Read JSON from stdin."""
    try:
        data = sys.stdin.read()
        return json.loads(data) if data.strip() else {}
    except Exception:
        return {}


def map_event_to_state(event: str, is_error: bool = False) -> str:
    """Map hook event to overlay state."""
    mapping = {
        'SessionStart': 'greeting',
        'PreToolUse': 'working',
        'PostToolUse': 'success' if not is_error else 'error',
        'Stop': 'celebrating',
        'Notification': 'idle',
    }
    return mapping.get(event, 'idle')


def detect_error(data: dict) -> bool:
    """Check if tool execution had an error."""
    result = data.get('tool_result', {})
    if isinstance(result, dict):
        if result.get('error'):
            return True
        output = str(result.get('output', ''))
    else:
        output = str(result)

    error_patterns = ['error:', 'Error:', 'ERROR', 'failed', 'ENOENT']
    return any(p in output for p in error_patterns)


def write_state(state: str, tool: str = None):
    """Write state to state file."""
    FX_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({
        'state': state,
        'tool': tool,
        'timestamp': int(__import__('time').time() * 1000)
    }))


def is_overlay_running() -> bool:
    """Check if overlay process is running."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text())
            os.kill(pid, 0)
            return True
        except (ValueError, ProcessLookupError, PermissionError):
            pass
    return False


def start_overlay():
    """Start overlay process in background."""
    overlay_script = PLUGIN_ROOT / 'scripts' / 'overlay.py'
    if overlay_script.exists():
        env = os.environ.copy()
        env['CLAUDE_FX_ROOT'] = str(PLUGIN_ROOT)
        subprocess.Popen(
            [sys.executable, str(overlay_script)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )


def play_sound(state: str):
    """Play sound for state (macOS)."""
    sounds = {
        'greeting': 'greeting.wav',
        'working': 'working.wav',
        'success': 'success.wav',
        'error': 'error.wav',
        'celebrating': 'celebration.wav',
    }
    sound_file = sounds.get(state)
    if not sound_file:
        return

    sound_path = PLUGIN_ROOT / 'themes' / 'default' / 'sounds' / sound_file
    if sound_path.exists():
        try:
            # macOS
            subprocess.Popen(
                ['afplay', '-v', '0.5', str(sound_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass


def main():
    # Read hook event
    data = read_stdin()
    event = data.get('hook_event_name', '')

    if not event:
        sys.exit(0)

    # Determine state
    is_error = event == 'PostToolUse' and detect_error(data)
    state = map_event_to_state(event, is_error)
    tool = data.get('tool_name')

    # Write state file
    write_state(state, tool)

    # Start overlay if not running
    if not is_overlay_running():
        start_overlay()

    # Play sound
    play_sound(state)

    # Always exit 0 to not block Claude
    sys.exit(0)


if __name__ == '__main__':
    main()
