#!/usr/bin/env python3
"""
Claude FX Hook Handler - Receives hook events and updates overlay state.
Includes setup checking on SessionStart.
"""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

# Session ID cache (terminal PID, set once per hook invocation)
_session_id = None

# Paths
HOME = Path.home()
FX_DIR = HOME / '.claude-fx'
SETUP_OK_FILE = FX_DIR / 'setup_ok'


def get_socket_path(session_id: int) -> Path:
    """Get socket file path for a session."""
    return FX_DIR / f'sock-{session_id}.sock'


def get_session_id() -> int | None:
    """Get session ID (terminal PID only - for singleton lock)."""
    global _session_id
    if _session_id is None:
        info = get_terminal_info()
        if info:
            # ALWAYS use PID for session ID (lock file)
            # Window ID is only for visibility tracking
            _session_id = info.get('pid')
    return _session_id


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


def send_state_to_overlay(state: str, tool: str = None) -> bool:
    """Send state update to overlay via socket. Returns True if successful."""
    session_id = get_session_id()
    if not session_id:
        return False

    socket_path = get_socket_path(session_id)
    if not socket_path.exists():
        return False

    # Get terminal info for visibility tracking
    info = get_terminal_info() or {}

    # Build message
    msg = {
        'cmd': 'SET_STATE',
        'state': state,
        'tool': tool,
        'terminal_pid': info.get('pid'),
        'terminal_window_id': info.get('window_id')
    }

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(0.5)  # 500ms timeout - don't block Claude
        sock.connect(str(socket_path))
        sock.sendall(f'{json.dumps(msg)}\n'.encode('utf-8'))
        response = sock.recv(1024).decode('utf-8').strip()
        sock.close()
        return response.startswith('{"status": "ok"}')
    except (socket.timeout, ConnectionRefusedError, FileNotFoundError):
        return False
    except Exception:
        return False


def is_overlay_running() -> bool:
    """Check if overlay is running by testing socket connection."""
    session_id = get_session_id()
    if not session_id:
        return False

    socket_path = get_socket_path(session_id)
    if not socket_path.exists():
        return False

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(0.1)  # Fast check
        sock.connect(str(socket_path))
        sock.sendall(b'{"cmd": "PING"}\n')
        response = sock.recv(64).decode('utf-8').strip()
        sock.close()
        return response == 'PONG'
    except Exception:
        return False


def shutdown_overlay():
    """Send shutdown command to overlay via socket."""
    session_id = get_session_id()
    if not session_id:
        return

    socket_path = get_socket_path(session_id)
    if not socket_path.exists():
        return

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(1.0)
        sock.connect(str(socket_path))
        sock.sendall(b'{"cmd": "SHUTDOWN"}\n')
        sock.recv(1024)  # Wait for ack
        sock.close()
    except Exception:
        pass  # Best effort


def cleanup_legacy_files():
    """Remove old state/pid/lock files from file-based IPC era."""
    if not FX_DIR.exists():
        return

    patterns = [
        'state-*.json', 'overlay-*.pid', 'overlay-*.lock',
        'state.json', 'overlay.pid', 'overlay.lock'
    ]

    for pattern in patterns:
        for f in FX_DIR.glob(pattern):
            try:
                f.unlink()
            except Exception:
                pass


def start_overlay():
    """Start session-specific overlay process in background."""
    session_id = get_session_id()
    if not session_id:
        return
    overlay_script = PLUGIN_ROOT / 'scripts' / 'overlay.py'
    if overlay_script.exists():
        env = os.environ.copy()
        env['CLAUDE_FX_ROOT'] = str(PLUGIN_ROOT)
        env['CLAUDE_FX_SESSION'] = str(session_id)  # Pass session ID
        subprocess.Popen(
            [sys.executable, str(overlay_script)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )


def load_manifest(theme: str) -> dict:
    """Load theme manifest.json."""
    manifest_path = PLUGIN_ROOT / 'themes' / theme / 'manifest.json'
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text())
        except Exception:
            pass
    return {}


# Supported audio formats on macOS (afplay)
AUDIO_EXTENSIONS = ('.wav', '.mp3', '.m4a', '.aiff', '.aif', '.caf', '.aac')


def find_sound_file(state: str, theme: str, manifest: dict) -> Path | None:
    """
    Find sound file for state. Priority:
    1. Manifest-specified path
    2. Sound file matching state name (e.g., greeting.wav for 'greeting')
    """
    sounds_dir = PLUGIN_ROOT / 'themes' / theme / 'sounds'

    # Check manifest first
    state_cfg = manifest.get('states', {}).get(state, {})
    manifest_sound = state_cfg.get('sound')
    if manifest_sound:
        sound_path = PLUGIN_ROOT / 'themes' / theme / manifest_sound
        if sound_path.exists():
            return sound_path

    # Fall back to state-named file (e.g., greeting.wav, greeting.mp3)
    if sounds_dir.exists():
        for ext in AUDIO_EXTENSIONS:
            sound_path = sounds_dir / f'{state}{ext}'
            if sound_path.exists():
                return sound_path

    return None


def play_sound(state: str, settings: dict):
    """Play sound for state (macOS). Uses afplay for native playback."""
    # Check if audio is enabled
    audio_cfg = settings.get('audio', {})
    if not audio_cfg.get('enabled', True):
        return

    volume = audio_cfg.get('volume', 0.5)
    theme = settings.get('theme', 'default')

    # Load manifest and find sound file
    manifest = load_manifest(theme)
    sound_path = find_sound_file(state, theme, manifest)

    if not sound_path:
        return

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
        # Clean up legacy files from old file-based IPC
        cleanup_legacy_files()

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

    # Handle SessionEnd - show farewell and shutdown overlay (non-blocking)
    if event == 'SessionEnd':
        send_state_to_overlay(state, tool)
        play_sound('farewell', settings)
        shutdown_overlay()
        sys.exit(0)

    # Send state to overlay via socket
    sent = send_state_to_overlay(state, tool)

    # Start overlay if not running and enabled
    if overlay_enabled and not sent and not is_overlay_running():
        start_overlay()
        # Give overlay time to start, then send state again
        time.sleep(0.3)
        send_state_to_overlay(state, tool)

    # Play sound
    play_sound(state, settings)

    # Always exit 0 to not block Claude
    sys.exit(0)


if __name__ == '__main__':
    main()
