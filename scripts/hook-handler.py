#!/usr/bin/env python3
"""
Claude FX Hook Handler - Receives hook events and updates overlay state.
Includes setup checking on SessionStart.
"""

import fcntl
import json
import os
import subprocess
import sys
from pathlib import Path

# Session window ID cache (set once per hook invocation)
_session_window_id = None

# Paths
HOME = Path.home()
FX_DIR = HOME / '.claude-fx'
SETUP_OK_FILE = FX_DIR / 'setup_ok'


def get_session_paths(window_id: int) -> tuple[Path, Path]:
    """Get session-specific state and PID file paths."""
    return (
        FX_DIR / f'state-{window_id}.json',
        FX_DIR / f'overlay-{window_id}.pid'
    )


def get_lock_file(window_id: int) -> Path:
    """Get lock file path for a session."""
    return FX_DIR / f'overlay-{window_id}.lock'


def get_session_id() -> int | None:
    """Get session ID (terminal PID only - for singleton lock)."""
    global _session_window_id
    if _session_window_id is None:
        info = get_terminal_info()
        if info:
            # ALWAYS use PID for session ID (lock file)
            # Window ID is only for visibility tracking
            _session_window_id = info.get('pid')
    return _session_window_id


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

    # Get window ID by enumerating terminal's windows (even if not frontmost)
    window_id = None
    try:
        from AppKit import NSWorkspace
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGWindowListOptionOnScreenOnly,
            kCGNullWindowID,
        )

        windows = CGWindowListCopyWindowInfo(
            kCGWindowListOptionOnScreenOnly, kCGNullWindowID
        )

        # Find windows belonging to our terminal PID (layer 0 = normal windows)
        terminal_windows = []
        for w in windows:
            if w.get('kCGWindowOwnerPID') == terminal_pid:
                layer = w.get('kCGWindowLayer', 0)
                if layer == 0:
                    terminal_windows.append(w.get('kCGWindowNumber'))

        if len(terminal_windows) == 1:
            # Only one window - use it
            window_id = terminal_windows[0]
        elif len(terminal_windows) > 1:
            # Multiple windows - check if one is frontmost
            frontmost = NSWorkspace.sharedWorkspace().frontmostApplication()
            if frontmost.processIdentifier() == terminal_pid:
                # Terminal is frontmost, first layer-0 window is active
                window_id = terminal_windows[0]
            # If not frontmost, can't reliably pick the right window
            # Leave window_id as None - overlay will detect it later
    except Exception:
        pass

    _terminal_info = {'pid': terminal_pid, 'window_id': window_id}
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
    """Write state to session-specific state file."""
    session_id = get_session_id()
    if not session_id:
        return  # Can't determine session
    state_file, _ = get_session_paths(session_id)
    FX_DIR.mkdir(parents=True, exist_ok=True)
    # Include terminal info for visibility tracking
    info = get_terminal_info() or {}
    state_file.write_text(json.dumps({
        'state': state,
        'tool': tool,
        'terminal_pid': info.get('pid'),
        'terminal_window_id': info.get('window_id'),
        'timestamp': int(__import__('time').time() * 1000)
    }))


def is_overlay_running() -> bool:
    """Check if overlay is running using lock file."""
    session_id = get_session_id()
    if not session_id:
        return False

    lock_file = get_lock_file(session_id)
    if not lock_file.exists():
        return False

    # Try to acquire lock - if we can't, overlay holds it
    try:
        fd = os.open(str(lock_file), os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Got lock - no overlay running, release it
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
            return False
        except BlockingIOError:
            os.close(fd)
            return True  # Lock held by overlay
    except Exception:
        return False


def stop_overlay():
    """Stop the session-specific overlay process and clean up files."""
    window_id = get_session_id()
    if not window_id:
        return
    state_file, pid_file = get_session_paths(window_id)
    lock_file = get_lock_file(window_id)

    # Try to get PID from lock file first, then fall back to pid file
    pid = None
    for f in [lock_file, pid_file]:
        if f.exists():
            try:
                pid = int(f.read_text().strip())
                break
            except (ValueError, OSError):
                pass

    if pid:
        try:
            os.kill(pid, 15)  # SIGTERM
        except (ProcessLookupError, PermissionError):
            pass

    # Clean up all files
    pid_file.unlink(missing_ok=True)
    lock_file.unlink(missing_ok=True)
    state_file.unlink(missing_ok=True)


def start_overlay():
    """Start session-specific overlay process in background."""
    window_id = get_session_id()
    if not window_id:
        return
    overlay_script = PLUGIN_ROOT / 'scripts' / 'overlay.py'
    if overlay_script.exists():
        env = os.environ.copy()
        env['CLAUDE_FX_ROOT'] = str(PLUGIN_ROOT)
        env['CLAUDE_FX_SESSION'] = str(window_id)  # Pass session ID
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
