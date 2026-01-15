#!/usr/bin/env python3
"""
Claude FX Hook Handler - Receives hook events and updates overlay state.
Includes setup checking on SessionStart.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Terminal PID cache (set once per session)
_terminal_pid = None

# Paths
HOME = Path.home()
FX_DIR = HOME / '.claude-fx'
STATE_FILE = FX_DIR / 'state.json'
PID_FILE = FX_DIR / 'overlay.pid'
SETUP_OK_FILE = FX_DIR / 'setup_ok'

PLUGIN_ROOT = Path(os.environ.get(
    'CLAUDE_PLUGIN_ROOT',
    Path(__file__).parent.parent
))

TERMINAL_NAMES = {
    'Terminal', 'iTerm2', 'Alacritty', 'kitty', 'Warp', 'WezTerm'
}

# Cache for terminal info
_terminal_info = None


def get_terminal_info() -> dict | None:
    """Get terminal PID and window ID for the terminal running Claude Code."""
    global _terminal_info
    if _terminal_info is not None:
        return _terminal_info

    # First, find terminal PID by walking process tree
    terminal_pid = None
    pid = os.getpid()
    while pid > 1:
        try:
            result = subprocess.run(
                ['ps', '-p', str(pid), '-o', 'ppid=,comm='],
                capture_output=True, text=True
            )
            parts = result.stdout.strip().split(None, 1)
            if len(parts) >= 2:
                ppid, comm = int(parts[0]), parts[1]
                if any(t.lower() in comm.lower() for t in TERMINAL_NAMES):
                    terminal_pid = pid
                    break
                pid = ppid
            else:
                break
        except Exception:
            break

    if not terminal_pid:
        return None

    # Now find the frontmost window for this terminal (the active one)
    try:
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGWindowListOptionOnScreenOnly,
            kCGNullWindowID,
        )
        windows = CGWindowListCopyWindowInfo(
            kCGWindowListOptionOnScreenOnly, kCGNullWindowID
        )
        # Find windows belonging to our terminal, pick the first (topmost)
        for w in windows:
            if w.get('kCGWindowOwnerPID') == terminal_pid:
                window_id = w.get('kCGWindowNumber')
                if window_id:
                    _terminal_info = {
                        'pid': terminal_pid,
                        'window_id': window_id
                    }
                    return _terminal_info
    except Exception:
        pass

    # Fallback: just PID, no window ID
    _terminal_info = {'pid': terminal_pid, 'window_id': None}
    return _terminal_info


def load_settings() -> dict:
    """Load settings from settings-fx.json."""
    settings_file = PLUGIN_ROOT / 'settings-fx.json'
    if settings_file.exists():
        try:
            return json.loads(settings_file.read_text())
        except Exception:
            pass
    return {}


def read_stdin() -> dict:
    """Read JSON from stdin."""
    try:
        data = sys.stdin.read()
        return json.loads(data) if data.strip() else {}
    except Exception:
        return {}


def check_setup() -> bool:
    """
    Check if setup is complete.
    Returns True if all requirements are met.
    """
    # Quick check - if setup_ok file exists, we're good
    if SETUP_OK_FILE.exists():
        return True

    # Run full setup check
    setup_script = PLUGIN_ROOT / 'scripts' / 'setup.py'
    if not setup_script.exists():
        return True  # No setup script, assume OK

    try:
        # Import and run setup check
        import importlib.util
        spec = importlib.util.spec_from_file_location("setup", setup_script)
        setup_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(setup_module)

        # Run check (quiet mode, no auto-install)
        return setup_module.main(force_check=True, quiet=False)
    except Exception as e:
        # If setup check fails, print error but don't block
        print(f"Setup check error: {e}", file=sys.stderr)
        return False


def map_event_to_state(event: str, is_error: bool = False) -> str:
    """Map hook event to overlay state."""
    mapping = {
        'SessionStart': 'greeting',
        'PreToolUse': 'working',
        'PostToolUse': 'success' if not is_error else 'error',
        'Stop': 'celebrating',
        'SessionEnd': 'farewell',
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
    terminal_info = get_terminal_info() or {}
    STATE_FILE.write_text(json.dumps({
        'state': state,
        'tool': tool,
        'terminal_pid': terminal_info.get('pid'),
        'terminal_window_id': terminal_info.get('window_id'),
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


def stop_overlay():
    """Stop the overlay process."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text())
            os.kill(pid, 15)  # SIGTERM
            PID_FILE.unlink()
        except (ValueError, ProcessLookupError, PermissionError):
            pass
        except FileNotFoundError:
            pass


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


def play_sound(state: str, settings: dict):
    """Play sound for state (macOS)."""
    # Check if audio is enabled
    audio_cfg = settings.get('audio', {})
    if not audio_cfg.get('enabled', True):
        return

    volume = audio_cfg.get('volume', 0.5)
    theme = settings.get('theme', 'default')

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

    sound_path = PLUGIN_ROOT / 'themes' / theme / 'sounds' / sound_file
    if sound_path.exists():
        try:
            subprocess.Popen(
                ['afplay', '-v', str(volume), str(sound_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass


def main():
    """Main entry point."""
    # Read hook event
    data = read_stdin()
    event = data.get('hook_event_name', '')

    if not event:
        sys.exit(0)

    # On SessionStart, check setup first
    if event == 'SessionStart':
        if not check_setup():
            # Setup incomplete - message already shown by setup.py
            # Don't start overlay, just exit
            sys.exit(0)

    # Skip overlay actions if setup not complete
    if not SETUP_OK_FILE.exists():
        sys.exit(0)

    # Load settings
    settings = load_settings()

    # Check if overlay is enabled
    overlay_cfg = settings.get('overlay', {})
    overlay_enabled = overlay_cfg.get('enabled', True)

    # Determine state
    is_error = event == 'PostToolUse' and detect_error(data)
    state = map_event_to_state(event, is_error)
    tool = data.get('tool_name')

    # Handle SessionEnd specially - show farewell then kill overlay
    if event == 'SessionEnd':
        write_state(state, tool)
        play_sound('greeting', settings)  # Play greeting sound for goodbye
        import time
        time.sleep(3.5)  # Wait for animation
        stop_overlay()
        sys.exit(0)

    # Write state file
    write_state(state, tool)

    # Start overlay if not running and enabled
    if overlay_enabled and not is_overlay_running():
        start_overlay()

    # Play sound
    play_sound(state, settings)

    # Always exit 0 to not block Claude
    sys.exit(0)


if __name__ == '__main__':
    main()
